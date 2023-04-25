# Run db-sync Docker Image on Windows Subsystem for Linux

In this guide you will set up WSL on your Windows, install Docker and run the db-sync docker image.

## Prerequisites

- PostGIS database
- Windows 10 version 2004 and higher (Build 19041 and higher) or Windows 11 or Windows Server 2022

If you have older system version see [manual install](https://learn.microsoft.com/en-us/windows/wsl/install-manual) 

## Install WSL and Ubuntu 

Open PowerShell or command prompt with administrative rights and the following command and restart your system:
```
wsl --install
```

If you have problems installing, see [Microsoft WSL Installation docs for desktops](https://learn.microsoft.com/en-us/windows/wsl/install)  or [server 2022](https://learn.microsoft.com/en-us/windows/wsl/install-on-server)

On VM servers, you need to enable nested virtualisation on the parent Hyper-V host, see [WSL FAQ](https://learn.microsoft.com/en-us/windows/wsl/faq#can-i-run-wsl-2-in-a-virtual-machine-).

You can now run your Ubuntu terminal from Windows Start menu and install Docker in WSL.

## Install Docker

In your WSL Ubuntu terminal: 
```
sudo apt install apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
sudo apt update
sudo apt-cache policy docker-ce
sudo apt install docker-ce
```
Check the installation:
```
sudo docker run hello-world
```
In case of problems consult [Docker on Ubuntu page](https://docs.docker.com/engine/install/ubuntu/).

## Running db-sync Docker Image

```
sudo docker run --name mergin_db_sync -it \
 -e MERGIN__USERNAME=JohnD \
 -e MERGIN__PASSWORD=MySecret \
 -e CONNECTIONS="[{driver='postgres', conn_info='host=myhost.com dbname=db-sync user=postgres password=top_secret', modified='sync_data', base='sync_base', mergin_project='john/db-sync', sync_file='sync_db.gpkg'}]" \
  lutraconsulting/mergin-db-sync:latest python3 dbsync_daemon.py --init-from-db
```
If you run PostgreSQL server on your Windows host machine you can use `$(hostname).local` as the host name.