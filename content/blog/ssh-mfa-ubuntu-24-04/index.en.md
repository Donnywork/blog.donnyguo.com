---
title: "SSH Key + TOTP: Two-Factor Authentication on Ubuntu 24.04"
date: 2026-10-23
description: "Require an SSH key and a TOTP code on Ubuntu 24.04, with PAM setup, client troubleshooting, recovery, and MFA removal."
authors: [donny]
categories: [Security]
tags: [SSH, Ubuntu, Linux, MFA, TOTP, DevOps]
images: [thumbnail.webp]
---

Goal: SSH login requires your key *and* a 6-digit code from Google Authenticator (or any TOTP app: Authy, 1Password, Aegis). The setup is a few lines, but three things along the way look like server bugs and aren't. They're covered in [Troubleshooting](#troubleshooting).

Tested on Ubuntu 24.04 with the stock OpenSSH. The second factor uses time-based one-time passwords (TOTP).[^totp]

## TL;DR

Server, `/etc/pam.d/sshd` (top of file):

```text
auth required pam_google_authenticator.so
# @include common-auth
```

Server, `/etc/ssh/sshd_config`:

```text
UsePAM yes
PubkeyAuthentication yes
KbdInteractiveAuthentication yes
AuthenticationMethods publickey,keyboard-interactive
```

Client, `~/.ssh/config` (only needed if your client doesn't offer the code prompt on its own, see [below](#permission-denied-keyboard-interactive-and-no-code-prompt)):

```text
Host your-server
    PreferredAuthentications publickey,keyboard-interactive
```

Don't just paste these in. Read the steps below first, mainly the part about keeping a session open.

## Before you touch anything

Keep one SSH session open the whole time and test from a second terminal. If PAM or sshd breaks, that open session is your way back in.

Also check your fallback: your provider's web console only helps if you can log in there, and many cloud images have no password set for any user. Set one for a sudo user now, or find out how your provider's rescue mode works.

Back up the two files you're about to edit:

```bash
sudo cp /etc/pam.d/sshd /etc/pam.d/sshd.bak
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
```

## 1. Install the PAM module

```bash
sudo apt update
sudo apt install libpam-google-authenticator
```

## 2. Enroll your user

Run this as the user who will log in, without sudo. Otherwise the secret lands in `/root`.

```bash
google-authenticator
```

Answer `y` to time-based tokens, scan the QR code, and **store the emergency scratch codes somewhere that isn't this server**. Sensible answers for the other prompts: update the file `y`, disallow token reuse `y`, widen the window `n`, rate limiting `y`.

To skip the questions, this does the same thing non-interactively:

```bash
google-authenticator -t -d -f -r 3 -R 30 -w 3
```

That creates `~/.google_authenticator`. Repeat for every user who logs in over SSH, including root if you allow root login. For root, also check `PermitRootLogin`: `prohibit-password` disables keyboard-interactive authentication for root.[^sshd]

## 3. PAM

Edit `/etc/pam.d/sshd`:

```text
auth required pam_google_authenticator.so
# @include common-auth
```

Commenting out `@include common-auth` drops the system password prompt, so the second factor is the code only (key + code). Leave it in if you want key + password + code.

Don't add `nullok` unless you're rolling this out gradually. With it, any user without a `~/.google_authenticator` file skips the code entirely, which is easy to miss when you test as the wrong user.[^pam]

## 4. sshd

In `/etc/ssh/sshd_config`:

```text
UsePAM yes
PubkeyAuthentication yes
KbdInteractiveAuthentication yes
AuthenticationMethods publickey,keyboard-interactive
```

`ChallengeResponseAuthentication` is an older name for `KbdInteractiveAuthentication`; use the latter on Ubuntu 24.04.

Check for overrides. Ubuntu includes `/etc/ssh/sshd_config.d/*.conf` at the top of the main file, and sshd uses the first value it finds, so a drop-in there can silently override what you just wrote.[^sshd] Look in that directory and compare against what's actually in effect:

```bash
sudo sshd -T | grep -Ei "authenticationmethods|kbdinteractive|usepam|passwordauth|pubkeyauth"
```

You want `authenticationmethods publickey,keyboard-interactive` and `kbdinteractiveauthentication yes`. If the login user falls under a `Match` block, check as that user:

```bash
sudo sshd -T -C user=youruser,host=localhost,addr=127.0.0.1 | grep -i authenticationmethods
```

## 5. Validate and restart

```bash
sudo mkdir -p /run/sshd
sudo sshd -t
sudo systemctl restart ssh
```

`sshd -t` prints nothing when the config is valid. The `mkdir` is explained in the first troubleshooting item.

## 6. Test from a new terminal

```bash
ssh -o ControlMaster=no -o ControlPath=none -v you@your-server
```

Expected: the key is accepted, then you get `Verification code:`. In the `-v` output:

```text
Authenticated using "publickey" with partial success.
Authentications that can continue: keyboard-interactive
```

Enter the code and you get a shell. Only close your original session after this works.

## Troubleshooting {#troubleshooting}

| Symptom | First thing to check |
| --- | --- |
| `sshd -t` reports a missing `/run/sshd` | Create the runtime directory, then validate again. |
| Login succeeds with only a key | Disable connection multiplexing for the test. |
| `Permission denied (keyboard-interactive)` with no prompt | Check the client's authentication preferences. |
| The code prompt appears, but the code is rejected | Check clocks, the login user, and the secret file. |

### `Missing privilege separation directory: /run/sshd`

`sshd -t` run by hand can fail with this. It isn't a config error.

Why a syntax check cares about a directory: sshd's privilege separation. Before authentication, sshd handles the connection in an unprivileged child process that chroots into an empty directory, `/run/sshd` on Debian/Ubuntu. sshd checks that this directory exists as part of its startup sanity checks, and test mode (`-t`) goes through the same startup path, so it fails when the directory is missing.

The directory is created by the `ssh` service when it starts and removed when it stops (`/run` is a tmpfs, so it's also gone after a reboot). Ubuntu 24.04 uses socket activation by default, so the service may simply not be running at that moment, and the directory doesn't exist.[^ubuntu]

```bash
sudo mkdir -p /run/sshd && sudo chmod 0755 /run/sshd
sudo sshd -t
```

Restarting the `ssh` service recreates the directory on its own.

### It let me in with just the key

You restart sshd, test, and get a shell with no code prompt. The config is probably fine. Your "new" session was likely multiplexed onto an existing connection (ControlMaster), so it never authenticated at all. Two common causes: `ControlMaster`/`ControlPersist` in your ssh config, and kitty's `kitten ssh`, which shares connections to the same server within one kitty instance (it uses SSH ControlMasters under the hood; the option is `share_connections`, and `close_shared_ssh_connections` drops them).[^kitty]

Bypass multiplexing when testing:

```bash
ssh -o ControlMaster=no -o ControlPath=none you@your-server
```

The server log shows what really happened:

```bash
sudo journalctl -u ssh -f
```

A genuine MFA login logs `Postponed publickey` followed by `Accepted keyboard-interactive/pam`. If nothing is logged when you "log in", you reused a connection.

### `Permission denied (keyboard-interactive)` and no code prompt {#permission-denied-keyboard-interactive-and-no-code-prompt}

With a fresh connection you may see this:

```text
debug1: Authenticated using "publickey" with partial success.
debug1: Authentications that can continue: keyboard-interactive
debug1: No more authentication methods to try.
Permission denied (keyboard-interactive).
```

The server accepted the key and asked for the second step. The client then never tried keyboard-interactive. So the problem is on the client side, not the server.

Normally OpenSSH offers keyboard-interactive on its own after a partial success, but some client setups don't. Whatever the cause, the fix is to tell the client explicitly. Try it on the command line first:

```bash
ssh -o PreferredAuthentications=publickey,keyboard-interactive you@your-server
```

You should get the `Verification code:` prompt right away. To make it permanent, put it in `~/.ssh/config`:

```text
Host your-server
    PreferredAuthentications publickey,keyboard-interactive
```

Use `Host *` to apply it everywhere. ssh config also takes the first value it finds, so a specific `Host` block has to come before `Host *`.[^ssh] To see what the client currently uses for a host:

```bash
ssh -G you@your-server | grep -i preferredauth
```

### Codes are rejected

- **Clock skew.** TOTP depends on time. Check `timedatectl` on the server for `System clock synchronized: yes`; fix with `sudo timedatectl set-ntp true`. Your phone's clock must be on automatic too.
- **Wrong user.** The secret file has to be in the home directory of the user you log in as, owned by them, normally with mode `0400`.[^pam]
- **Logs.** `sudo journalctl -u ssh -n 50` or `/var/log/auth.log` shows `Invalid verification code` or a failure to read the file.

## Recovery {#recovery}

Lost your phone: use a scratch code (each works once), then re-run `google-authenticator` to generate a new secret.

Locked out with no open session: log in through your provider's web console (it uses the local login prompt, not sshd's PAM stack, so it needs a local password) and restore the backups:

```bash
sudo cp /etc/pam.d/sshd.bak /etc/pam.d/sshd
sudo cp /etc/ssh/sshd_config.bak /etc/ssh/sshd_config
sudo sshd -t && sudo systemctl restart ssh
```

## Removing MFA

Same rules as the install: keep a working session open and test from a second terminal.

### Quick off switch (reversible)

Do both edits. Commenting out only the PAM line leaves sshd asking for keyboard-interactive with nothing behind it, and logins fail.

1. In `/etc/pam.d/sshd`, comment out the module:

   ```
   # auth required pam_google_authenticator.so
   ```

2. In `/etc/ssh/sshd_config`, fall back to key-only:

   ```
   AuthenticationMethods publickey
   ```

3. Validate and restart:

   ```bash
   sudo sshd -t && sudo systemctl restart ssh
   ```

To turn it back on, undo both edits. Nobody has to re-enroll, since the `~/.google_authenticator` files are still there.

### Off for one user only

Keep the global setup and add a `Match` block at the **end** of `sshd_config` (everything after a `Match` line belongs to it):

```text
Match User deploy
    AuthenticationMethods publickey
```

Validate, restart, and check that it applies:

```bash
sudo sshd -t && sudo systemctl restart ssh
sudo sshd -T -C user=deploy,host=localhost,addr=127.0.0.1 | grep -i authenticationmethods
```

### Full removal

The order matters. If you uninstall the package while `pam_google_authenticator.so` is still in `/etc/pam.d/sshd`, PAM can't load the module and logins start failing.

1. **Remove the PAM line**, or restore the backup:

   ```bash
   sudo cp /etc/pam.d/sshd.bak /etc/pam.d/sshd
   ```

2. **Edit `sshd_config`** for key-only login:

   ```
   AuthenticationMethods publickey
   KbdInteractiveAuthentication no
   ```

   Don't just delete the `AuthenticationMethods` line. Without it sshd falls back to its defaults, which may allow password login again depending on your other settings. If you want passwords off, set `PasswordAuthentication no` explicitly.

3. **Look for leftovers** in drop-ins and `Match` blocks:

   ```bash
   sudo grep -rniE "authenticationmethods|kbdinteractive" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/
   ```

4. **Validate, restart, test from a new terminal:**

   ```bash
   sudo sshd -t && sudo systemctl restart ssh
   ssh -o ControlMaster=no -o ControlPath=none -v you@your-server
   ```

   You should get a shell right after the key is accepted, with no `Verification code:` prompt. Don't continue until this works.

5. **Delete the secrets** for every enrolled user:

   ```bash
   rm ~/.google_authenticator
   sudo rm /home/otheruser/.google_authenticator
   sudo rm /root/.google_authenticator   # if you enrolled root
   ```

   Delete the entry in your authenticator app too.

6. **Uninstall the module:**

   ```bash
   sudo apt remove --purge libpam-google-authenticator
   sudo apt autoremove
   ```

7. **Clean up the client.** Remove the `PreferredAuthentications` line (or the whole `Host` block) from `~/.ssh/config` if it was only there for MFA.

If you get locked out partway through, use the console and restore the `.bak` files as described in [Recovery](#recovery).

## References

Use `man sshd_config`, `man ssh_config`, and `man pam_google_authenticator` on the server or client for documentation matching the installed version.

[^pam]: [Google Authenticator PAM module](https://github.com/google/google-authenticator-libpam): enrollment, module options such as `nullok`, secret-file ownership and permissions, and `required` versus `requisite`.
[^sshd]: [Ubuntu 24.04 `sshd_config(5)`](https://manpages.ubuntu.com/manpages/noble/en/man5/sshd_config.5.html): `AuthenticationMethods`, `KbdInteractiveAuthentication`, `UsePAM`, `PermitRootLogin`, and `Match`. See also the [upstream OpenSSH manual](https://man.openbsd.org/sshd_config).
[^ssh]: [Ubuntu 24.04 `ssh_config(5)`](https://manpages.ubuntu.com/manpages/noble/en/man5/ssh_config.5.html): `PreferredAuthentications`, `ControlMaster`, and `ControlPath`. See also the [upstream OpenSSH manual](https://man.openbsd.org/ssh_config).
[^ubuntu]: [SSHd now uses socket-based activation (Ubuntu 22.10 and later)](https://discourse.ubuntu.com/t/sshd-now-uses-socket-based-activation-ubuntu-22-10-and-later/30189/1): Ubuntu's socket activation defaults and the changes in 24.04.
[^totp]: [RFC 6238](https://datatracker.ietf.org/doc/html/rfc6238) defines TOTP, building on the HOTP algorithm in [RFC 4226](https://datatracker.ietf.org/doc/html/rfc4226). Compatible authenticator apps implement the same standards.
[^kitty]: [kitty's SSH kitten documentation](https://sw.kovidgoyal.net/kitty/kittens/ssh/#ssh-configuration): connection sharing through `share_connections` and `close_shared_ssh_connections`.
