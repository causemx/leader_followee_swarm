import argparse
import socket,time,os
import threading
import sys
import control_func
from decimal import *


s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

statusKeyWithSubkeys = [
    'GPS_RAW_INT-lat'
    ,'GPS_RAW_INT-lon'
    ,'GLOBAL_POSITION_INT-relative_alt'             # 20
    ,'GLOBAL_POSITION_INT-hdg'                      #yaw
]

def udp_listener():
    s.bind(("",24550))
    while True :
        try :
            data,addr=s.recvfrom(1024)
            data = data.decode()
            print(data)
        except :
            continue

def cmd_sending(cmd):
    s.sendto(cmd.encode('utf-8'),("192.168.3.255",24551))

def boardcast_pos_loop():
    while True :
        pos_data = "leaderPos"
        leader_status = responses()
        if leader_status != "":
            pos_data += leader_status
            cmd_sending(pos_data)
        time.sleep(0.1)

def responses():
    cust_status = control_func.GetStatus()
    try:
        res_str = ""
        status_path = r"/home/pi/status.txt"
        if os.path.isfile(status_path):
            status = cust_status.readContent(status_path)
            if status != "":
                for i in range(len(statusKeyWithSubkeys)):
                    entry = statusKeyWithSubkeys[i].split('-')[0]
                    subKey = statusKeyWithSubkeys[i].split('-')[1]
                    if subKey == "lat" or subKey == "lon" :
                        temp = Decimal(cust_status.get_status(entry,subKey,status)) / Decimal(1e7)
                        res_str += ' ' + str(temp)
                    elif subKey == "relative_alt" :
                        temp = Decimal(cust_status.get_status(entry,subKey,status)) / Decimal(1000)
                        res_str += ' ' + str(temp)
                    elif subKey == subKey == "hdg" :
                        temp = Decimal(cust_status.get_status(entry,subKey,status)) / Decimal(100)
                        res_str += ' ' + str(temp)
    except Exception as e:
        print(e)
    return res_str


def handle_takeoff(args):
    cmd_sending("takeoff")

def handle_land(args):
    cmd_sending("land")

def handle_mode(args):
    mode = args.mode
    mode_map = control_func.mode_mapping()
    if mode_map is None or mode not in mode_map:
        print(f"Unknown mode '{mode}'")
    else:
        cmd_sending(f"mode {mode}")

def handle_line_up(args):
    cmd_sending("line up")

def handle_follow(args):
    if args.state == "on":
        cmd_sending("follow on")
    elif args.state == "off":
        cmd_sending("follow off")

def build_parser():
    parser = argparse.ArgumentParser(prog="Gateway CMD")
    subparsers = parser.add_subparsers(dest="command")

    # takeoff
    parser_takeoff = subparsers.add_parser("takeoff")
    parser_takeoff.set_defaults(func=handle_takeoff)

    # land
    parser_land = subparsers.add_parser("land")
    parser_land.set_defaults(func=handle_land)

    # mode
    parser_mode = subparsers.add_parser("mode")
    parser_mode.add_argument("mode", type=str)
    parser_mode.set_defaults(func=handle_mode)

    # line up
    parser_line = subparsers.add_parser("line")
    parser_line.add_argument("direction", choices=["up"])
    parser_line.set_defaults(func=handle_line_up)

    # follow
    parser_follow = subparsers.add_parser("follow")
    parser_follow.add_argument("state", choices=["on", "off"])
    parser_follow.set_defaults(func=handle_follow)

    return parser

def main():
    parser = build_parser()

    udp_service = threading.Thread(target = udp_listener)
    udp_service.start()
    udp_service.join(2)
    time.sleep(0.2)

    pos_service = threading.Thread(target = boardcast_pos_loop)
    pos_service.start()
    pos_service.join(2)
    time.sleep(0.2)

    while True:
        try:
            inputdata = input("[*]Gateway:\t")
            if not inputdata.strip():
                continue

            args = parser.parse_args(inputdata.split())

            if hasattr(args, "func"):
                args.func(args)
            else:
                parser.print_help()

        except SystemExit:
            # prevent argparse from exiting loop
            continue
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
