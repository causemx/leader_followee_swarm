import argparse
import socket
import time
import threading
import sys
import zmq

import control_func

from decimal import Decimal

# UDP Broadcast Socket

s = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM,
    socket.IPPROTO_UDP
)

s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

# ZeroMQ Subscriber

context = zmq.Context()
socket_sub = context.socket(zmq.SUB)

# connect to telemetry publisher
socket_sub.connect("tcp://127.0.0.1:5556")
# subscribe all topics
socket_sub.setsockopt_string(zmq.SUBSCRIBE, "")
latest_status = {}


def zmq_listener():
    global latest_status

    while True:
        try:
            latest_status = socket_sub.recv_json()
        except Exception as e:
            print("[ZMQ ERROR]", e)
            time.sleep(0.1)


def udp_listener():
    s.bind(("", 24550))
    while True:
        try:
            data, addr = s.recvfrom(1024)
            data = data.decode()
            print(data)
        except:
            continue


def cmd_sending(cmd):
    s.sendto(
        cmd.encode('utf-8'),
        ("192.168.3.255", 24551)
    )


def responses():
    global latest_status

    try:
        if not latest_status:
            return ""

        lat = latest_status.get("lat", 0)
        lon = latest_status.get("lon", 0)
        relative_alt = latest_status.get("relative_alt", 0)
        hdg = latest_status.get("hdg", 0)

        res_str = ""

        res_str += " " + str(lat)
        res_str += " " + str(lon)
        res_str += " " + str(relative_alt)
        res_str += " " + str(hdg)

        return res_str
    except Exception as e:
        print("[RESPONSES ERROR]", e)
        return ""


def boardcast_pos_loop():
    while True:
        try:
            pos_data = "leaderPos"
            leader_status = responses()
            if leader_status != "":
                pos_data += leader_status
                cmd_sending(pos_data)
                print("[Broadcast]", pos_data)

            time.sleep(0.1)
        except Exception as e:
            print("[Broadcast ERROR]", e)
            time.sleep(0.1)


# Command Handlers

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


# CLI Parser

def build_parser():
    parser = argparse.ArgumentParser(
        prog="Gateway CMD"
    )

    subparsers = parser.add_subparsers(
        dest="command"
    )

    # takeoff
    parser_takeoff = subparsers.add_parser(
        "takeoff"
    )

    parser_takeoff.set_defaults(
        func=handle_takeoff
    )

    # land
    parser_land = subparsers.add_parser(
        "land"
    )

    parser_land.set_defaults(
        func=handle_land
    )

    # mode
    parser_mode = subparsers.add_parser(
        "mode"
    )

    parser_mode.add_argument(
        "mode",
        type=str
    )

    parser_mode.set_defaults(
        func=handle_mode
    )

    # line up
    parser_line = subparsers.add_parser(
        "line"
    )

    parser_line.add_argument(
        "direction",
        choices=["up"]
    )

    parser_line.set_defaults(
        func=handle_line_up
    )

    # follow
    parser_follow = subparsers.add_parser(
        "follow"
    )

    parser_follow.add_argument(
        "state",
        choices=["on", "off"]
    )

    parser_follow.set_defaults(
        func=handle_follow
    )

    return parser


def main():

    parser = build_parser()

    # Start ZeroMQ Listener

    zmq_thread = threading.Thread(
        target=zmq_listener,
        daemon=True
    )

    zmq_thread.start()

    # Start UDP Listener

    udp_service = threading.Thread(
        target=udp_listener,
        daemon=True
    )

    udp_service.start()

    # Start Broadcast Loop

    pos_service = threading.Thread(
        target=boardcast_pos_loop,
        daemon=True
    )

    pos_service.start()

    while True:
        try:
            inputdata = input("[*]Gateway>>")
            if not inputdata.strip():
                continue
            args = parser.parse_args(
                inputdata.split()
            )
            if hasattr(args, "func"):
                args.func(args)
            else:
                parser.print_help()

        except SystemExit:
            continue
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            print("[MAIN ERROR]", e)


if __name__ == "__main__":
    main()
