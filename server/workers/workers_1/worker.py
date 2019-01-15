#!/usr/bin/env python3

import os
import sys
import time
import redis
import subprocess

import datetime

def data_incorrect_format(session_uuid):
    print('Incorrect format')
    sys.exit(1)

redis_server = redis.StrictRedis(
                    host="localhost",
                    port=6379,
                    db=0)

type = 1
tcp_dump_cycle = '300'
stream_buffer = 100

id_to_delete = []

if __name__ == "__main__":

    if len(sys.argv) != 2:
        print('usage:', 'Worker.py', 'session_uuid')
        exit(1)

    session_uuid = sys.argv[1]
    stream_name = 'stream:{}:{}'.format(type, session_uuid)
    consumer_name = 'consumer:{}:{}'.format(type, session_uuid)
    group_name = 'workers:{}:{}'.format(type, session_uuid)
    id = '0'

    res = redis_server.xread({stream_name: id}, count=1)
    if res:
        uuid = res[0][1][0][1][b'uuid'].decode()
        date = datetime.datetime.now().strftime("%Y%m%d")
        tcpdump_path = os.path.join('../../data', uuid, str(type))
        rel_path = os.path.join(tcpdump_path, date[0:4], date[4:6], date[6:8])
        if not os.path.isdir(rel_path):
            os.makedirs(rel_path)
    else:
        sys.exit(1)
        print('Incorrect message')
    redis_server.sadd('working_session_uuid:{}'.format(type), session_uuid)

    #LAUNCH a tcpdump
    process = subprocess.Popen(["tcpdump", '-n', '-r', '-', '-G', tcp_dump_cycle, '-w', '{}/%Y/%m/%d/{}-%Y-%m-%d-%H%M%S.cap'.format(tcpdump_path, uuid)], stdin=subprocess.PIPE)
    nb_save = 0

    while True:
        #redis_server.sadd('working_session_uuid:{}'.format(type), session_uuid)

        res = redis_server.xread({stream_name: id}, count=1)
        if res:
            new_id = res[0][1][0][0].decode()
            if id != new_id:
                id = new_id
                data = res[0][1][0][1]
                if id and data:
                    #print(id)
                    #print(data)
                    new_date = datetime.datetime.now().strftime("%Y%m%d")
                    if new_date != date:
                        date= new_date
                        rel_path = os.path.join(tcpdump_path, date[0:4], date[4:6], date[6:8])
                        if not os.path.isdir(rel_path):
                            os.makedirs(rel_path)

                    try:
                        process.stdin.write(data[b'message'])
                        id_to_delete.append(id)
                    except:
                        Error_message = process.stderr.read()
                        if Error_message == b'tcpdump: unknown file format\n':
                            data_incorrect_format(session_uuid)

                        #print(process.stdout.read())
                    nb_save += 1

                    if nb_save > stream_buffer:
                        for id in id_to_delete:
                            redis_server.xdel(stream_name, id)
                        id_to_delete = []
                        nb_save = 0

        else:
            # sucess, all data are saved
            if redis_server.sismember('ended_session', session_uuid):
                out, err = process.communicate(timeout= 0.5)
                #print(out)
                if err == b'tcpdump: unknown file format\n':
                    data_incorrect_format(session_uuid)
                elif err:
                    print(err)

                #print(process.stderr.read())
                redis_server.srem('ended_session', session_uuid)
                redis_server.srem('session_uuid:{}'.format(type), session_uuid)
                redis_server.srem('working_session_uuid:{}'.format(type), session_uuid)
                redis_server.hdel('map-type:session_uuid-uuid:{}'.format(type), session_uuid)
                redis_server.delete(stream_name)
                # make sure that tcpdump can save all datas
                time.sleep(int(tcp_dump_cycle) + 1)
                print('tcpdump: {} Done'.format(session_uuid))
                sys.exit(0)
            else:
                time.sleep(10)
