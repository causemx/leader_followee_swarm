# Swarm control framework for leader-followee architecture

## Prerequisites
Check the ModemManager is active? If yes, stop it and disable or remove it.

```bash
# Remove the modemmanager, it will takeover serial port
sudo apt purge modemmanager
sudo apt autoremove
```

## Dependency
* pymavlink
* mavproxy
* future
* zeroMQ
```
sudo apt update
sudo apt install libzmq3-dev
sudo apt install python3-zmq
```
## Flight control connection
Add below line into .bashrc(Must confirm the mavproxy has been installed)
```
sudo mavproxy.py --master=/dev/ttyAMA0 --baudrate=57600 --out=tcpin:0.0.0.0:14551 --out=udpin:0.0.0.0:14553 > /dev/null 2>&1
```
