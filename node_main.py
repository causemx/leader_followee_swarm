import socket
import time
import threading
import control_func

from enum import Enum

# =========================
# CONFIG / GLOBAL STATE
# =========================
UDP_PORT_LISTEN = 24551
UDP_PORT_SEND = 24550
LEADER_IP = "192.168.3.2"
TARGET_IP = LEADER_IP

FollowMode = 0
mode = "-1"

# =========================
# MANUAL CONFIG
# =========================

MY_IP = control_func.get_lan_ip()

print(f"[*] Current IP: {MY_IP}")

DRONE_CONFIG = { 
    "192.168.3.2": {
        "id": 1,
        "role": "leader"
    },  
    "192.168.3.3": {
        "id": 2,
        "role": "follower"
    },  
    "192.168.3.4": {
        "id": 3,
        "role": "follower"
    }
}

drone_ID = DRONE_CONFIG[MY_IP]["id"]
DRONE_ROLE = DRONE_CONFIG[MY_IP]["role"]


# =========================
# ENUMS
# =========================
class DRONE_HEADER(Enum):
    TURNED = 1
    KEEP = 0


class DroneFormationMapping(Enum):
    A_FORMATION = ([0, 0, 0], [-300, -300, 0], [300, -300, 0])


# =========================
# SOCKET SETUP
# =========================
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)


# =========================
# HELPERS
# =========================
def parse_message(data):
    return data.strip().split()


def valid_position(data):
    return all(v != " " for v in data)


def update_follower_position(leader_data):
    global drone_ID

    if DRONE_ROLE == "leader":
        return

    formation = DroneFormationMapping.A_FORMATION.value[drone_ID - 1]

    control_func.set_target_position_baseline(
        leader_data[0],
        leader_data[1],
        formation[0],
        formation[1],
        str(float(leader_data[2]) + formation[2]),
        leader_data[3],
        DRONE_HEADER.TURNED.value
    )


# =========================
# UDP LISTENER
# =========================
def udp_listener(drone_ID):
    global FollowMode

    leader = [" "] * 4
    last_leader = [" "] * 4

    sock.bind(("", UDP_PORT_LISTEN))

    while True:
        try:
            data, _ = sock.recvfrom(1024)
            parts = parse_message(data.decode())

            if not parts:
                continue

            cmd = parts[0]

            if cmd == "takeoff":
                print("Receive cmd: takeoff")
                control_func.auto_take_off()

            elif cmd == "land":
                print("Receive cmd: land")
                control_func.set_mode_apm("LAND")

            elif cmd == "mode":
                print("Receive cmd: mode")
                control_func.set_mode_apm(parts[1])

            elif cmd == "follow":
                print("Receive cmd: follow")
                FollowMode = 1 if parts[1] == "on" else 0

            elif cmd == "line" and parts[1] == "up":
                print("Receive cmd: line up")
                if valid_position(leader) and valid_position(last_leader):
                    control_func.set_yaw(leader[3], 1, 1, 0)

                    if FollowMode:
                        update_follower_position(leader)

            elif cmd == "leaderPos":
                leader = parts[1:5]

                if " " in last_leader:
                    last_leader = leader

                if valid_position(leader) and valid_position(last_leader):
                    moved = (
                        control_func.checkDis(leader, last_leader) > 0.8 or
                        abs(float(leader[2]) - float(last_leader[2])) > 0.8 or
                        abs(float(leader[3]) - float(last_leader[3])) > 10
                    )

                    if FollowMode and moved:
                        update_follower_position(leader)

                last_leader = leader

        except Exception as e:
            print(f"[Listener Error] {e}")


# =========================
# RESPONSE LOOP
# =========================
def responser_loop():
    global FollowMode, drone_ID, mode

    while True:
        try:
            res_data = f"{drone_ID},{FollowMode}"
            stat_data = control_func.responses(str(drone_ID))

            if stat_data:
                mode = stat_data.split(',')[10]
                res_data += stat_data

                print(res_data)
                sock.sendto(res_data.encode(), (TARGET_IP, UDP_PORT_SEND))

            time.sleep(1)

        except Exception as e:
            print(f"[Responder Error] {e}")



# =========================
# MAIN
# =========================
if __name__ == "__main__":

    listener_thread = threading.Thread(
        target=udp_listener, args=(drone_ID,), daemon=True
    )
    responder_thread = threading.Thread(
        target=responser_loop, daemon=True
    )

    listener_thread.start()
    responder_thread.start()

    listener_thread.join()
    responder_thread.join()
