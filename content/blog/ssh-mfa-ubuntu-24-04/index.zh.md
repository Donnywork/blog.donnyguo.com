---
title: "在 Ubuntu 24.04 上为 SSH 配置密钥 + TOTP 双因素认证"
date: 2026-10-23
description: "在 Ubuntu 24.04 上让 SSH 登录同时验证密钥和 TOTP 动态验证码，涵盖 PAM 配置、客户端排错、恢复访问与移除 MFA。"
authors: [donny]
categories: [Security]
tags: [SSH, Ubuntu, Linux, MFA, TOTP, DevOps]
images: [thumbnail.webp]
---

目标：SSH 登录时，既要验证密钥，*也要*输入 Google Authenticator 或其他 TOTP 应用（如 Authy、1Password、Aegis）生成的六位验证码。配置本身只有几行，但过程中有三个现象很像服务器出了问题，实际上并非如此，后面的[排错](#troubleshooting)部分会逐一说明。

本文在 Ubuntu 24.04 自带的 OpenSSH 上测试。第二个因素使用基于时间的一次性密码（TOTP）。[^totp]

## 配置速览

服务器上的 `/etc/pam.d/sshd`（文件顶部）：

```text
auth required pam_google_authenticator.so
# @include common-auth
```

服务器上的 `/etc/ssh/sshd_config`：

```text
UsePAM yes
PubkeyAuthentication yes
KbdInteractiveAuthentication yes
AuthenticationMethods publickey,keyboard-interactive
```

客户端的 `~/.ssh/config`（仅在客户端没有自动显示验证码提示时需要，见[下文](#permission-denied-keyboard-interactive-and-no-code-prompt)）：

```text
Host your-server
    PreferredAuthentications publickey,keyboard-interactive
```

不要直接粘贴后就重启服务。先读完下面的步骤，尤其是保留一个已登录会话的部分。

## 动手之前

整个过程中，始终保留一个已登录的 SSH 会话，再从第二个终端测试。如果 PAM 或 sshd 配错，这个会话就是修复配置的退路。

还要确认备用入口是否可用：云服务商的网页控制台只有在你能登录系统时才有用，而很多云镜像没有为任何用户设置密码。现在就为一个有 sudo 权限的用户设置本地密码，或者先弄清楚服务商的救援模式如何使用。

备份即将修改的两个文件：

```bash
sudo cp /etc/pam.d/sshd /etc/pam.d/sshd.bak
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
```

## 1. 安装 PAM 模块

```bash
sudo apt update
sudo apt install libpam-google-authenticator
```

## 2. 为登录用户配置验证器

以实际通过 SSH 登录的用户执行下面的命令，**不要加 sudo**，否则密钥文件会放进 `/root`。

```bash
google-authenticator
```

选择基于时间的验证码时回答 `y`，扫描二维码，并将**应急备用码保存到这台服务器以外的地方**。其余提示可依次选择：更新文件 `y`、禁止重复使用同一个验证码 `y`、扩大时间窗口 `n`、启用速率限制 `y`。

如果想跳过交互提问，下面的命令可以完成相同配置：

```bash
google-authenticator -t -d -f -r 3 -R 30 -w 3
```

命令会创建 `~/.google_authenticator`。每个通过 SSH 登录的用户都需要单独执行；如果允许 root 登录，也需要为 root 配置。此外，root 还受 `PermitRootLogin` 限制：设置为 `prohibit-password` 时，root 的 keyboard-interactive 认证也会被禁用。[^sshd]

## 3. 配置 PAM

编辑 `/etc/pam.d/sshd`：

```text
auth required pam_google_authenticator.so
# @include common-auth
```

注释掉 `@include common-auth` 会去掉系统账户密码提示，让第二步只验证动态验证码，即“密钥 + 验证码”。如果希望同时要求“密钥 + 系统密码 + 验证码”，就保留这一行。

除非正在分批部署，否则不要添加 `nullok`。加上它之后，任何没有 `~/.google_authenticator` 文件的用户都会跳过验证码；如果测试时用了另一个用户，很容易漏掉这个问题。[^pam]

## 4. 配置 sshd

在 `/etc/ssh/sshd_config` 中设置：

```text
UsePAM yes
PubkeyAuthentication yes
KbdInteractiveAuthentication yes
AuthenticationMethods publickey,keyboard-interactive
```

`ChallengeResponseAuthentication` 是 `KbdInteractiveAuthentication` 的旧名称；在 Ubuntu 24.04 上使用后者。

检查是否有其他配置抢先生效。Ubuntu 在主配置文件顶部包含 `/etc/ssh/sshd_config.d/*.conf`，而 sshd 通常使用最先读到的值，因此这个目录里的配置可能让你刚修改的值无法生效。[^sshd] 查看目录中的文件，再检查实际生效的配置：

```bash
sudo sshd -T | grep -Ei "authenticationmethods|kbdinteractive|usepam|passwordauth|pubkeyauth"
```

应当能看到 `authenticationmethods publickey,keyboard-interactive` 和 `kbdinteractiveauthentication yes`。如果登录用户会命中某个 `Match` 块，还要按该用户的条件检查：

```bash
sudo sshd -T -C user=youruser,host=localhost,addr=127.0.0.1 | grep -i authenticationmethods
```

## 5. 验证并重启

```bash
sudo mkdir -p /run/sshd
sudo sshd -t
sudo systemctl restart ssh
```

配置有效时，`sshd -t` 不会输出任何内容。为什么需要 `mkdir`，见排错的第一项。

## 6. 从新终端测试

```bash
ssh -o ControlMaster=no -o ControlPath=none -v you@your-server
```

预期行为：先接受密钥，然后出现 `Verification code:` 提示。开启 `-v` 后会看到：

```text
Authenticated using "publickey" with partial success.
Authentications that can continue: keyboard-interactive
```

输入验证码后应能进入 shell。只有确认成功后，才能关闭最初保留的会话。

## 排错 {#troubleshooting}

| 现象 | 优先检查 |
| --- | --- |
| `sshd -t` 提示缺少 `/run/sshd` | 创建运行时目录，再验证一次。 |
| 只验证密钥就登录成功 | 测试时禁用连接复用。 |
| 没有验证码提示，直接出现 `Permission denied (keyboard-interactive)` | 检查客户端的认证方式偏好。 |
| 能看到验证码提示，但验证码不被接受 | 检查时钟、登录用户和密钥文件。 |

### `Missing privilege separation directory: /run/sshd`

手动运行 `sshd -t` 时可能出现这个错误。它不代表配置语法有问题。

为什么语法检查还要关心一个目录？原因是 sshd 的权限分离机制。认证前，sshd 会通过一个非特权子进程处理连接，并将其 chroot 到空目录中；在 Debian/Ubuntu 上，这个目录就是 `/run/sshd`。sshd 启动时会检查目录是否存在，测试模式（`-t`）也会经过同样的启动检查，因此目录缺失时就会失败。

这个目录会在 `ssh` 服务启动时创建，停止时移除；`/run` 本身是 tmpfs，重启后也不会保留目录。Ubuntu 24.04 默认使用 socket 激活，因此当时服务可能尚未运行，目录也就不存在。[^ubuntu]

```bash
sudo mkdir -p /run/sshd && sudo chmod 0755 /run/sshd
sudo sshd -t
```

重启 `ssh` 服务时，它也会自行重新创建该目录。

### 只验证密钥就让我登录了

重启 sshd 后测试，却没有验证码提示，直接进入了 shell。配置可能没有问题：所谓的“新”会话很可能复用了已有连接（ControlMaster），因此根本没有重新认证。常见来源有两个：SSH 配置里的 `ControlMaster`/`ControlPersist`，以及 kitty 的 `kitten ssh`。后者会在同一个 kitty 实例内共享到同一服务器的连接，底层也是 SSH ControlMaster；相关选项是 `share_connections`，可以用 `close_shared_ssh_connections` 断开共享连接。[^kitty]

测试时绕过连接复用：

```bash
ssh -o ControlMaster=no -o ControlPath=none you@your-server
```

服务器日志可以帮助确认实际发生了什么：

```bash
sudo journalctl -u ssh -f
```

真正经过 MFA 的登录会记录 `Postponed publickey`，随后是 `Accepted keyboard-interactive/pam`。如果“登录”时没有任何新增记录，说明复用了已有连接。

### `Permission denied (keyboard-interactive)`，没有验证码提示 {#permission-denied-keyboard-interactive-and-no-code-prompt}

使用全新连接时，可能会看到：

```text
debug1: Authenticated using "publickey" with partial success.
debug1: Authentications that can continue: keyboard-interactive
debug1: No more authentication methods to try.
Permission denied (keyboard-interactive).
```

服务器已经接受密钥，并要求执行第二步；但客户端没有继续尝试 keyboard-interactive。此时应该检查客户端。

正常情况下，OpenSSH 会在部分认证成功后自行尝试 keyboard-interactive，但某些客户端配置不会这样做。可以先在命令行上明确指定认证方式：

```bash
ssh -o PreferredAuthentications=publickey,keyboard-interactive you@your-server
```

这时应当出现 `Verification code:` 提示。要永久生效，在 `~/.ssh/config` 中加入：

```text
Host your-server
    PreferredAuthentications publickey,keyboard-interactive
```

如果想应用到所有主机，可以使用 `Host *`。SSH 客户端配置同样采用最先读到的值，因此具体主机的 `Host` 块要放在 `Host *` 前面。[^ssh] 查看某台主机当前使用的客户端配置：

```bash
ssh -G you@your-server | grep -i preferredauth
```

### 验证码被拒绝

- **时钟偏差。** TOTP 依赖时间。运行 `timedatectl`，检查服务器是否显示 `System clock synchronized: yes`；可用 `sudo timedatectl set-ntp true` 启用时间同步。手机也应开启自动设置时间。
- **用户不对。** 密钥文件必须位于实际登录用户的主目录中，由该用户拥有，权限通常为 `0400`。[^pam]
- **查看日志。** `sudo journalctl -u ssh -n 50` 或 `/var/log/auth.log` 中可能记录了 `Invalid verification code`，或读取密钥文件失败的原因。

## 恢复访问 {#recovery}

手机丢失时：使用应急备用码登录（每个只能用一次），再重新运行 `google-authenticator` 生成新的密钥。

如果已经被锁在外面，也没有保留的会话：通过云服务商的网页控制台登录。它使用系统本地登录流程，不经过 sshd 的 PAM 栈，因此需要本地账户密码。然后恢复备份：

```bash
sudo cp /etc/pam.d/sshd.bak /etc/pam.d/sshd
sudo cp /etc/ssh/sshd_config.bak /etc/ssh/sshd_config
sudo sshd -t && sudo systemctl restart ssh
```

## 移除 MFA

与安装时一样：保留一个可用的会话，再从第二个终端测试。

### 快速关闭（可恢复）

下面两处都要改。只注释 PAM 模块行，会让 sshd 继续要求 keyboard-interactive，却没有相应模块完成验证，导致登录失败。

1. 在 `/etc/pam.d/sshd` 中注释模块行：

   ```text
   # auth required pam_google_authenticator.so
   ```

2. 在 `/etc/ssh/sshd_config` 中改为仅验证密钥：

   ```text
   AuthenticationMethods publickey
   ```

3. 验证并重启：

   ```bash
   sudo sshd -t && sudo systemctl restart ssh
   ```

要重新开启，撤销这两处修改即可。用户不需要重新配置验证器，因为 `~/.google_authenticator` 文件还在。

### 只对一个用户关闭

保留全局配置，在 `sshd_config` 的**末尾**加入一个 `Match` 块。注意：`Match` 行之后的配置都属于这个条件块。

```text
Match User deploy
    AuthenticationMethods publickey
```

验证、重启，再确认该用户的设置已经生效：

```bash
sudo sshd -t && sudo systemctl restart ssh
sudo sshd -T -C user=deploy,host=localhost,addr=127.0.0.1 | grep -i authenticationmethods
```

### 彻底移除

顺序很重要。如果 `/etc/pam.d/sshd` 中还保留着 `pam_google_authenticator.so`，就先卸载软件包，PAM 会因无法加载模块而拒绝登录。

1. **移除 PAM 模块行**，或者恢复备份：

   ```bash
   sudo cp /etc/pam.d/sshd.bak /etc/pam.d/sshd
   ```

2. **修改 `sshd_config`**，让登录只验证密钥：

   ```text
   AuthenticationMethods publickey
   KbdInteractiveAuthentication no
   ```

   不要直接删除 `AuthenticationMethods` 行。删除后 sshd 会回到默认行为，取决于其他设置，可能重新允许密码登录。如果希望禁用密码认证，应显式设置 `PasswordAuthentication no`。

3. **检查其他配置文件和 `Match` 块中是否有残留：**

   ```bash
   sudo grep -rniE "authenticationmethods|kbdinteractive" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/
   ```

4. **验证、重启，并从新终端测试：**

   ```bash
   sudo sshd -t && sudo systemctl restart ssh
   ssh -o ControlMaster=no -o ControlPath=none -v you@your-server
   ```

   接受密钥后应直接进入 shell，不再出现 `Verification code:` 提示。确认成功后再继续。

5. **删除每个已配置用户的密钥文件：**

   ```bash
   rm ~/.google_authenticator
   sudo rm /home/otheruser/.google_authenticator
   sudo rm /root/.google_authenticator   # if you enrolled root
   ```

   同时删除验证器应用中的对应条目。

6. **卸载模块：**

   ```bash
   sudo apt remove --purge libpam-google-authenticator
   sudo apt autoremove
   ```

7. **清理客户端配置。** 如果 `~/.ssh/config` 中的 `PreferredAuthentications` 行（或整个 `Host` 块）仅为 MFA 添加，可以将它删除。

如果中途无法登录，通过控制台恢复 `.bak` 文件，操作见[恢复访问](#recovery)。

## 参考资料

在服务器或客户端上运行 `man sshd_config`、`man ssh_config` 和 `man pam_google_authenticator`，可以查阅与已安装版本对应的文档。

[^pam]: [Google Authenticator PAM 模块](https://github.com/google/google-authenticator-libpam)：验证器配置、`nullok` 等模块选项、密钥文件的所有者与权限要求，以及 `required` 与 `requisite` 的区别。
[^sshd]: [Ubuntu 24.04 `sshd_config(5)`](https://manpages.ubuntu.com/manpages/noble/en/man5/sshd_config.5.html)：`AuthenticationMethods`、`KbdInteractiveAuthentication`、`UsePAM`、`PermitRootLogin` 和 `Match`。另见 [OpenSSH 上游手册](https://man.openbsd.org/sshd_config)。
[^ssh]: [Ubuntu 24.04 `ssh_config(5)`](https://manpages.ubuntu.com/manpages/noble/en/man5/ssh_config.5.html)：`PreferredAuthentications`、`ControlMaster` 和 `ControlPath`。另见 [OpenSSH 上游手册](https://man.openbsd.org/ssh_config)。
[^ubuntu]: [SSHd now uses socket-based activation (Ubuntu 22.10 and later)](https://discourse.ubuntu.com/t/sshd-now-uses-socket-based-activation-ubuntu-22-10-and-later/30189/1)：Ubuntu 默认使用 socket 激活的背景，以及 24.04 的变化。
[^totp]: [RFC 6238](https://datatracker.ietf.org/doc/html/rfc6238) 定义了 TOTP，基于 [RFC 4226](https://datatracker.ietf.org/doc/html/rfc4226) 中的 HOTP 算法；兼容的验证器应用实现的是同一套标准。
[^kitty]: [kitty SSH kitten 官方文档](https://sw.kovidgoyal.net/kitty/kittens/ssh/#ssh-configuration)：`share_connections` 和 `close_shared_ssh_connections` 的连接共享行为。
