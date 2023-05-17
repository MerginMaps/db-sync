# Run db-sync Docker Image on Windows Subsystem for Linux

In this guide you will set up WSL on your Windows, install Docker and run the db-sync docker image.

## Prerequisites

- PostGIS database
- Windows 10 version 2004 and higher (Build 19041 and higher) or Windows 11 or Windows Server 2022

If you have older system version see [manual install](https://learn.microsoft.com/en-us/windows/wsl/install-manual)

## Install WSL and Ubuntu

Open PowerShell or command prompt with administrative rights and the following command and restart your system:

```bash
wsl --install
```

If you have problems installing, see [Microsoft WSL Installation docs for desktops](https://learn.microsoft.com/en-us/windows/wsl/install)  or [server 2022](https://learn.microsoft.com/en-us/windows/wsl/install-on-server)

On VM servers, you need to enable nested virtualisation on the parent Hyper-V host, see [WSL FAQ](https://learn.microsoft.com/en-us/windows/wsl/faq#can-i-run-wsl-2-in-a-virtual-machine-).

You can now run your Ubuntu terminal from Windows Start menu and install Docker in WSL.

## Install Docker

In your WSL Ubuntu terminal:

```bash
sudo apt install apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
sudo apt update
sudo apt-cache policy docker-ce
sudo apt install docker-ce
```

Check the installation:

```bash
sudo docker run hello-world
```

In case of problems consult [Docker on Ubuntu page](https://docs.docker.com/engine/install/ubuntu/).

## Running db-sync Docker Image

After the steps above, you can run the docker image as described in [Running with Docker](docker.md).

If you run PostgreSQL server on your Windows host machine you can use `$(hostname).local` as the host name.
