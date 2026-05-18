import os
import socket
import fcntl
import struct
import time
import datetime
import numbers
import threading
import json
import enum
import binascii
import zmq
import numpy as np

from MissionUtil import MissionUtil
from v20 import ardupilotmega
from numpy import radians, sin, cos, arcsin, sqrt

modname = ardupilotmega.MAVLink(0, 0, 0, False)
mavlink = ardupilotmega

host = "127.0.0.1"
port = 14553

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# ZeroMQ Subscriber

context = zmq.Context()
socket_sub = context.socket(zmq.SUB)
socket_sub.connect("tcp://127.0.0.1:5556")

# subscribe all topics
socket_sub.setsockopt_string(zmq.SUBSCRIBE, "")
latest_status = {}


global message, message_end, drone_status

message = ' '
message_end = ' '
drone_status = ""


def zmq_status_listener():
    global latest_status

    while True:
        try:
            latest_status = socket_sub.recv_json()

        except Exception as e:
            print("[ZMQ ERROR]", e)
            time.sleep(0.1)


# start background telemetry listener
status_thread = threading.Thread(
    target=zmq_status_listener,
    daemon=True
)

status_thread.start()


def get_interface_ip(ifname):
    get_s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    return socket.inet_ntoa(
        fcntl.ioctl(
            get_s.fileno(),
            0x8915,
            struct.pack(
                '256s',
                bytes(os.path.basename(ifname[:15]).encode('utf-8'))
            )
        )[20:24]
    )


def get_lan_ip():
    ip = socket.gethostbyname(socket.gethostname())

    if ip.startswith('127.') and os.name != 'nt':
        interfaces = ["wlan0"]
        for ifname in interfaces:
            try:
                ip = get_interface_ip(ifname)
                break
            except:
                pass

    return ip


def check_cmd(parm):
    if drone_status != "":
        print(f"[DUBG] drone_status: {drone_status}")
        if int(drone_status.split(',')[10]) == parm:
            return "success!"
        else:
            return "fail!"
    else:
        return "fail!"


def command_send(cmd_hex):
    temp = bytearray.fromhex(cmd_hex)
    s.sendto(temp, (host, port))


def receive_from_main(mainstatus, mainstatus_end):
    global message, message_end

    message = mainstatus
    message_end = mainstatus_end


def responses(id):
    global drone_status
    global latest_status

    try:
        if not latest_status:
            return ""

        res_str = ""

        res_str += "," + str(latest_status.get("battery", 0))
        res_str += "," + str(latest_status.get("satellites_visible", 0))
        res_str += "," + str(latest_status.get("fix_type", 0))
        res_str += "," + str(latest_status.get("lat", 0))
        res_str += "," + str(latest_status.get("lon", 0))
        res_str += "," + str(latest_status.get("compass_variance", 0))
        res_str += "," + str(latest_status.get("alt", 0))
        res_str += "," + str(latest_status.get("relative_alt", 0))
        res_str += "," + str(latest_status.get("safety_switch", 0))
        res_str += "," + str(latest_status.get("mode", 0))
        res_str += "," + str(latest_status.get("ekf_flags", 0))
        res_str += "," + str(latest_status.get("hdg", 0))

        now = datetime.datetime.now()
        now_unix = time.mktime(now.timetuple())
        res_str += "," + str(now_unix)
        drone_status = id + res_str

        return res_str

    except Exception as e:
        print("[RESPONSES ERROR]", e)
        return ""


def send_CMD(msg):
    bufStrWoSpaces = binascii.hexlify(bytearray(msg)).upper()
    print(bufStrWoSpaces)
    return s.sendto(msg, (host, port))


mode_mapping_acm = {
    0: 'STABILIZE',
    1: 'ACRO',
    2: 'ALT_HOLD',
    3: 'AUTO',
    4: 'GUIDED',
    5: 'LOITER',
    6: 'RTL',
    7: 'CIRCLE',
    8: 'POSITION',
    9: 'LAND',
    10: 'OF_LOITER',
    11: 'DRIFT',
    13: 'SPORT',
    14: 'FLIP',
    15: 'AUTOTUNE',
    16: 'POSHOLD',
    17: 'BRAKE',
    18: 'THROW',
    19: 'AVOID_ADSB',
    20: 'GUIDED_NOGPS',
    21: 'SMART_RTL',
    22: 'FLOWHOLD',
    23: 'FOLLOW',
    24: 'ZIGZAG',
    25: 'SYSTEMID',
    26: 'AUTOROTATE',
    27: 'AUTO_RTL',
}

mode_mapping_sub = {
    0: 'STABILIZE',
    1: 'ACRO',
    2: 'ALT_HOLD',
    3: 'AUTO',
    4: 'GUIDED',
    7: 'CIRCLE',
    9: 'SURFACE',
    16: 'POSHOLD',
    19: 'MANUAL',
}

AP_MAV_TYPE_MODE_MAP = {
    mavlink.MAV_TYPE_HELICOPTER: mode_mapping_acm,
    mavlink.MAV_TYPE_TRICOPTER: mode_mapping_acm,
    mavlink.MAV_TYPE_QUADROTOR: mode_mapping_acm,
    mavlink.MAV_TYPE_HEXAROTOR: mode_mapping_acm,
    mavlink.MAV_TYPE_OCTOROTOR: mode_mapping_acm,
    mavlink.MAV_TYPE_DECAROTOR: mode_mapping_acm,
    mavlink.MAV_TYPE_DODECAROTOR: mode_mapping_acm,
    mavlink.MAV_TYPE_COAXIAL: mode_mapping_acm,
    mavlink.MAV_TYPE_SUBMARINE: mode_mapping_sub,
}


def mode_mapping_byname(mav_type):
    mode_map = mode_mapping_bynumber(mav_type)

    if mode_map is None:
        return None

    inv_map = dict((a, b) for (b, a) in mode_map.items())

    return inv_map


def mode_mapping_bynumber(mav_type):
    return AP_MAV_TYPE_MODE_MAP[mav_type] \
        if mav_type in AP_MAV_TYPE_MODE_MAP else None


def mode_mapping():
    mav_type = mavlink.MAV_TYPE_QUADROTOR

    return mode_mapping_byname(mav_type)


def set_mode_apm(mode, custom_mode=0, custom_sub_mode=0):
    if isinstance(mode, str):
        mode_map = mode_mapping()

        if mode_map is None or mode not in mode_map:
            print("Unknown mode '%s'" % mode)
            return

        mode = mode_map[mode]

    msg = modname.command_long_encode(
        1,
        0,
        mavlink.MAV_CMD_DO_SET_MODE,
        0,
        mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode,
        0,
        0,
        0,
        0,
        0
    )

    buf = msg.pack(modname, False)

    send_CMD(buf)

    set_result = "fail!"

    for i in range(3):
        set_result = check_cmd(mode)

        if set_result == "success!":
            break

        elif set_result == "fail!":
            continue

        time.sleep(1)

    return "set mode " + set_result


def arducopter_arm():
    msg = modname.command_long_encode(
        1,
        0,
        mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1,
        0,
        0,
        0,
        0,
        0,
        0
    )

    buf = msg.pack(modname, False)
    send_CMD(buf)

    return "sent arm success!"


def arducopter_disarm():
    msg = modname.command_long_encode(
        1,
        0,
        mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0
    )

    buf = msg.pack(modname, False)
    send_CMD(buf)

    return "sent disarm success!"


def take_off_CMD(alt):
    altitude = float(alt)

    msg = modname.command_long_encode(
        0,
        0,
        mavlink.MAV_CMD_NAV_TAKEOFF,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        altitude
    )

    buf = msg.pack(modname, False)
    send_CMD(buf)

    return "sent take off success!"


def auto_take_off():
    set_mode_apm("GUIDED")
    arducopter_arm()
    time.sleep(1)
    arducopter_arm()
    time.sleep(3)
    take_off_CMD(5)
    return "sent take off success!"


class DRONE_YAW_DIRECTION(enum.IntEnum):
    COUNTER_CLOCKWISE = -1
    CLOCKWISE = 1


class DRONE_YAW_RELATIVE(enum.IntEnum):
    ABSOLUTE_ANGLE = 0
    RELATIVE_OFFECT = 1


def set_yaw(angle, speed, direction, relative):
    deg = float(angle)
    spd = float(speed)
    direct = float(direction)
    rela = float(relative)

    msg = modname.command_long_encode(
        1,
        0,
        mavlink.MAV_CMD_CONDITION_YAW,
        0,
        deg,
        spd,
        direct,
        rela,
        0,
        0,
        0
    )

    buf = msg.pack(modname, False)
    send_CMD(buf)

    return "sent condition yaw success!"


class DRONE_HEADER(enum.IntEnum):
    TURNED = 1
    KEEP = 0


def set_position_target_CMD_encode(
        type_mask,
        lat,
        lon,
        altitude,
        yaw,
        yaw_rate):

    msg = modname.set_position_target_global_int_encode(
        0,
        1,
        0,
        mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        type_mask,
        lat,
        lon,
        altitude,
        0,
        0,
        0,
        0,
        0,
        0,
        yaw,
        yaw_rate
    )

    buf = msg.pack(modname, False)
    send_CMD(buf)

    return "sent target CMD success!"


def set_target_position_baseline(
        begin_lat,
        begin_lng,
        x_axis,
        y_axis,
        alt,
        leader_yaw,
        head_frame):

    mission_util = MissionUtil(
        'udpout',
        '127.0.0.1',
        '14552'
    )

    baseline_lat_lng = [999, 999]

    baseline_lat_lng[0] = float(begin_lat)
    baseline_lat_lng[1] = float(begin_lng)

    altitude = float(alt)

    shift_deg = float(leader_yaw)

    print("deg from leader = " + str(shift_deg))

    latlng = mission_util.cal_latlng_by_baseline(
        x_axis,
        y_axis,
        baseline_lat_lng,
        shift_deg
    )

    lat = int(latlng[0] * 1e7)
    lon = int(latlng[1] * 1e7)

    print("lat,lon=" + str(latlng[0]) + "," + str(latlng[1]))

    if head_frame == DRONE_HEADER.TURNED.value:
        type_mask = 0b0000111111111000
        yaw = 0
        yaw_rate = 0
    elif head_frame == DRONE_HEADER.KEEP.value:
        type_mask = 0b0000001111111000
        yaw = np.deg2rad(float(shift_deg))
        yaw_rate = 5

    return set_position_target_CMD_encode(
        type_mask,
        lat,
        lon,
        altitude,
        yaw,
        yaw_rate
    )


def dis_cal(d_lon, d_lat, k):
    aa = sin(d_lat / 2) ** 2 + k * sin(d_lon / 2) ** 2
    bb = sqrt(aa)
    c = 2 * arcsin(bb)
    return c


def checkDis(pos1, pos2):
    lat1 = float(pos1[0])
    lon1 = float(pos1[1])
    lat2 = float(pos2[0])
    lon2 = float(pos2[1])

    lon1, lat1, lon2, lat2 = map(
        radians,
        [lon1, lat1, lon2, lat2]
    )

    d_lon = lon2 - lon1
    d_lat = lat2 - lat1

    k = cos(lat1) * cos(lat2)
    c = dis_cal(d_lon, d_lat, k)
    r = 6371

    return c * r * 1000