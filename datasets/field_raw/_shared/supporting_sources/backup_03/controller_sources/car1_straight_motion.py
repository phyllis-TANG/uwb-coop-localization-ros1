#!/usr/bin/env python2
"""Car1 straight-motion pilot. Dry run unless --execute is given.

Uses /car1/odom for relative displacement and publishes /car1/cmd_vel.
There is no obstacle avoidance; clear and supervise the path. The odometry
target is not a surveyed position or an independent distance reference.
"""
from __future__ import print_function

import argparse
import math
import sys
import time


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def control(start, pose, distance, speed):
    dx, dy = pose[0] - start[0], pose[1] - start[1]
    progress = dx * math.cos(start[2]) + dy * math.sin(start[2])
    lateral = -dx * math.sin(start[2]) + dy * math.cos(start[2])
    yaw_error = wrap(start[2] - pose[2])
    if distance - progress <= .025:
        return 0., 0., True, progress, lateral
    angular = max(-.12, min(.12, 1.2 * yaw_error - .5 * lateral))
    return speed, angular, False, progress, lateral


def self_test():
    start = (0., 0., math.pi / 2)
    pose = [0., 0., math.pi / 2]
    for _ in range(1000):
        v, w, done, progress, lateral = control(start, pose, 1., .045)
        if done:
            break
        pose[0] += v * math.cos(pose[2]) * .05
        pose[1] += v * math.sin(pose[2]) * .05
        pose[2] = wrap(pose[2] + w * .05)
    assert done and .975 <= progress <= 1.025
    assert control(start, start, 1., .045)[2] is False
    print('PASS: 1 m odom-feedback straight control and stop.')


class Controller(object):
    def __init__(self, args):
        import rospy
        import rosgraph
        from geometry_msgs.msg import Twist
        from nav_msgs.msg import Odometry
        self.ros = rospy
        self.Twist = Twist
        self.args = args
        self.pose = None
        self.received = None
        self.armed = False
        self.master = rosgraph.Master(rospy.get_name())
        self.next_graph_check = 0.
        self.check_graph()
        self.pub = rospy.Publisher('/car1/cmd_vel', Twist, queue_size=1)
        self.sub = rospy.Subscriber('/car1/odom', Odometry, self.callback, queue_size=1)
        rospy.on_shutdown(self.stop)

    def check_graph(self):
        publishers, subscribers, _ = self.master.getSystemState()
        others = [node for topic, nodes in publishers if topic == '/car1/cmd_vel'
                  for node in nodes if node != self.ros.get_name()]
        if others:
            raise RuntimeError('Stop other /car1/cmd_vel publishers: ' + ', '.join(others))
        base = any(topic == '/car1/cmd_vel' and '/car1/wheeltec_robot' in nodes
                   for topic, nodes in subscribers)
        if not base:
            raise RuntimeError('/car1/wheeltec_robot subscriber missing')

    def callback(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        values = (p.x, p.y, q.x, q.y, q.z, q.w)
        if not all(not (math.isnan(v) or math.isinf(v)) for v in values):
            return
        norm = math.sqrt(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w)
        if norm < .5 or norm > 1.5:
            return
        x, y, z, w = q.x/norm, q.y/norm, q.z/norm, q.w/norm
        yaw = math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
        self.pose = (p.x, p.y, yaw)
        self.received = time.time()

    def fresh(self):
        if self.ros.is_shutdown():
            raise RuntimeError('ROS shutdown')
        if self.received is None or time.time() - self.received > .5:
            raise RuntimeError('Odom missing or stale for more than 0.5 s')
        if time.time() >= self.next_graph_check:
            self.check_graph()
            self.next_graph_check = time.time() + 1.
            if self.pub.get_num_connections() == 0:
                raise RuntimeError('No /car1/cmd_vel subscriber')
        return self.pose

    def publish(self, linear=0., angular=0.):
        msg = self.Twist()
        msg.linear.x, msg.angular.z = linear, angular
        self.pub.publish(msg)

    def stop(self):
        if self.armed:
            for _ in range(10):
                try:
                    self.publish()
                except Exception:
                    break
                time.sleep(.05)

    def wait_ready(self):
        until = time.time() + 5.
        while self.received is None or self.pub.get_num_connections() == 0:
            if self.ros.is_shutdown() or time.time() > until:
                raise RuntimeError('Odom or cmd_vel subscriber not ready within 5 s')
            time.sleep(.05)
        self.fresh()
        self.armed = True

    def pause(self, seconds):
        until = time.time() + seconds
        while time.time() < until:
            self.fresh()
            self.publish()
            time.sleep(.05)

    def run(self):
        try:
            self.wait_ready()
            print('Ready: holding zero velocity for 5 s before forward motion.')
            sys.stdout.flush()
            self.pause(5.)
            start = self.fresh()
            until = time.time() + self.args.distance / self.args.speed + 25.
            best, last_progress = 0., time.time()
            while True:
                pose = self.fresh()
                v, w, done, progress, lateral = control(
                    start, pose, self.args.distance, self.args.speed)
                if progress < -.03 or abs(lateral) > .12 or abs(wrap(pose[2]-start[2])) > math.radians(20):
                    raise RuntimeError('Reverse progress, lateral drift or heading deviation')
                if done:
                    self.publish()
                    print('Stopped: odom projected distance %.3f m; lateral %.3f m' %
                          (progress, lateral))
                    sys.stdout.flush()
                    break
                if progress > best + .005:
                    best, last_progress = progress, time.time()
                if time.time() > until or time.time() - last_progress > 5.:
                    raise RuntimeError('Motion timed out or no progress for 5 s')
                self.publish(v, w)
                time.sleep(.05)
            self.pause(5.)
            print('Completed according to odom feedback; measure antenna endpoint.')
        finally:
            self.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--distance', type=float, default=1.)
    parser.add_argument('--speed', type=float, default=.045)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not (0 < args.distance <= 1.5 and .03 <= args.speed <= .06):
        parser.error('distance must be (0,1.5] m; speed [0.03,0.06] m/s')
    print('Car1 forward %.2f m at %.3f m/s (odom feedback)' %
          (args.distance, args.speed))
    if not args.execute:
        print('DRY RUN: no ROS node or command. Add --execute only when ready.')
        return
    import rospy
    rospy.init_node('car1_straight_motion', anonymous=True)
    if rospy.get_param('/use_sim_time', False):
        raise RuntimeError('Physical run requires use_sim_time=false')
    Controller(args).run()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted; zero velocity requested.')
        raise SystemExit(130)
    except Exception as error:
        print('ABORTED: %s' % error)
        raise SystemExit(1)
