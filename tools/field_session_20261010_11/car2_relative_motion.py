#!/usr/bin/env python3
"""Car2 ROS Noetic relative motion pilot. Dry-run unless --execute is supplied.

Feedback: /car2/odom. Commands: /car2/cmd_vel. Run on Car2 itself.
Stop the keyboard publisher first. No obstacle avoidance or global localization.
Distance/angle tolerances describe Odom feedback, not independently verified truth.
"""
import argparse
import math
import time


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def limit(value, bound):
    return max(-bound, min(bound, value))


def forward_control(start, current, distance, speed, tolerance):
    dx, dy = current[0] - start[0], current[1] - start[1]
    progress = dx * math.cos(start[2]) + dy * math.sin(start[2])
    cross = -dx * math.sin(start[2]) + dy * math.cos(start[2])
    remaining = distance - progress
    if remaining <= tolerance:
        return 0.0, 0.0, True, cross, progress
    desired = start[2] - math.atan2(cross, 0.5)
    error = wrap(desired - current[2])
    velocity = min(speed, max(0.025, 0.7 * remaining))
    if abs(error) > math.radians(20):
        velocity = 0.0
    return velocity, limit(error, 0.15), False, cross, progress


def turn_control(target, yaw, speed, tolerance):
    error = wrap(target - yaw)
    if abs(error) <= tolerance:
        return 0.0, True, error
    command = min(speed, max(0.05, abs(error)))
    return math.copysign(command, error), False, error


def self_test():
    # Integrate a simple unicycle, including a turn across the +/- pi boundary.
    pose = [0.0, 0.0, math.radians(-170)]
    origin = list(pose)
    for _ in range(1600):
        v, w, done, cross, progress = forward_control(origin, pose, 1., .045, .025)
        if done:
            break
        pose[0] += v * math.cos(pose[2]) * .05
        pose[1] += v * math.sin(pose[2]) * .05
        pose[2] = wrap(pose[2] + w * .05)
    assert done and abs(progress - 1.) <= .0251
    target = wrap(pose[2] - math.pi / 2)
    for _ in range(1600):
        w, done, error = turn_control(target, pose[2], .15, math.radians(2))
        if done:
            break
        pose[2] = wrap(pose[2] + w * .05)
    assert done and abs(wrap(target - pose[2])) <= math.radians(2)
    assert forward_control(origin, origin, 1., .045, .025)[2] is False
    assert turn_control(target, target, .15, math.radians(2))[0] == 0
    print('PASS: simulated forward motion, 90-degree turn, angle wrap and stop targets.')


class Controller:
    def __init__(self, args):
        import rospy
        import rosgraph
        from geometry_msgs.msg import Twist
        from nav_msgs.msg import Odometry
        self.ros, self.Twist, self.args = rospy, Twist, args
        self.pose, self.received, self.seq = None, None, 0
        self.master = rosgraph.Master(rospy.get_name())
        self.topic = '/car2/cmd_vel'
        self.next_graph_check = 0.0
        self.armed = False
        self.check_graph()
        self.pub = rospy.Publisher(self.topic, Twist, queue_size=1)
        self.sub = rospy.Subscriber('/car2/odom', Odometry, self.callback, queue_size=1)
        rospy.on_shutdown(self.stop)

    def check_graph(self):
        publishers, subscribers, _ = self.master.getSystemState()
        others = [node for topic, nodes in publishers if topic == self.topic
                  for node in nodes if node != self.ros.get_name()]
        if others:
            raise RuntimeError('Stop other cmd_vel publishers first: ' + ', '.join(others))
        base_present = any(topic == self.topic and '/car2/wheeltec_robot' in nodes
                           for topic, nodes in subscribers)
        if not base_present:
            raise RuntimeError('Expected /car2/wheeltec_robot subscriber is missing')

    def callback(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        values = (p.x, p.y, q.x, q.y, q.z, q.w)
        if not all(math.isfinite(v) for v in values):
            return
        norm = math.sqrt(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w)
        if norm < .5 or norm > 1.5:
            return
        x, y, z, w = q.x/norm, q.y/norm, q.z/norm, q.w/norm
        yaw = math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
        self.pose = (p.x, p.y, yaw)
        self.received = time.monotonic()
        self.seq += 1

    def fresh(self):
        if self.ros.is_shutdown():
            raise RuntimeError('ROS shutdown')
        if self.received is None or time.monotonic() - self.received > .5:
            raise RuntimeError('Odom missing or stale for more than 0.5 s')
        if time.monotonic() >= self.next_graph_check:
            self.check_graph()
            self.next_graph_check = time.monotonic() + 1.
            if self.pub.get_num_connections() == 0:
                raise RuntimeError('No cmd_vel subscriber')
        return self.pose

    def publish(self, linear=0., angular=0.):
        msg = self.Twist()
        msg.linear.x, msg.angular.z = linear, angular
        self.pub.publish(msg)

    def stop(self):
        if self.armed and hasattr(self, 'pub'):
            for _ in range(5):
                try:
                    self.publish()
                except Exception:
                    break
                time.sleep(.02)

    def wait_ready(self):
        until = time.monotonic() + 5.
        while self.received is None or self.pub.get_num_connections() == 0:
            if self.ros.is_shutdown() or time.monotonic() > until:
                raise RuntimeError('Odom or cmd_vel subscriber not ready within 5 s')
            time.sleep(.05)
        self.fresh()
        self.armed = True

    def pause(self, seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            self.fresh()
            self.publish()
            time.sleep(.05)

    def forward(self):
        start = self.fresh()
        until = time.monotonic() + self.args.distance/self.args.linear_speed + 25.
        best, last_progress = 0., time.monotonic()
        while True:
            pose = self.fresh()
            v, w, done, cross, progress = forward_control(
                start, pose, self.args.distance, self.args.linear_speed, .025)
            if abs(cross) > .15:
                raise RuntimeError('Cross-track deviation exceeded 0.15 m')
            if done:
                self.publish()
                print('Forward stopped: projected distance %.3f m; lateral %.3f m' %
                      (progress, cross), flush=True)
                return
            if progress > best + .005:
                best, last_progress = progress, time.monotonic()
            if time.monotonic() > until or time.monotonic() - last_progress > 5.:
                raise RuntimeError('Forward timeout or no progress for 5 s')
            self.publish(v, w)
            time.sleep(.05)

    def turn(self):
        initial = self.fresh()[2]
        target = wrap(initial + math.radians(self.args.turn_deg))
        until = time.monotonic() + abs(math.radians(self.args.turn_deg))/self.args.turn_speed + 25.
        best, changed = abs(math.radians(self.args.turn_deg)), time.monotonic()
        settled, last_seq = 0, -1
        while True:
            pose = self.fresh()
            w, done, error = turn_control(target, pose[2], self.args.turn_speed, math.radians(2))
            if done:
                self.publish()
                if self.seq != last_seq:
                    settled += 1
                    last_seq = self.seq
                if settled >= 5:
                    print('Turn stopped: heading change %+.1f deg; target error %+.1f deg' %
                          (math.degrees(wrap(pose[2]-initial)), math.degrees(error)), flush=True)
                    return
            else:
                settled = 0
                self.publish(0., w)
            if abs(error) < best - math.radians(.5):
                best, changed = abs(error), time.monotonic()
            if time.monotonic() > until or (not done and time.monotonic()-changed > 5.):
                raise RuntimeError('Turn timeout or no angular progress for 5 s')
            time.sleep(.05)

    def run(self):
        try:
            self.wait_ready()
            print('Ready. Holding zero velocity for 5 s before starting.', flush=True)
            self.pause(5.)
            if not self.args.turn_only:
                print('First forward segment', flush=True)
                self.forward()
                self.pause(5.)
            print('Turn segment', flush=True)
            self.turn()
            self.pause(5.)
            if not self.args.turn_only:
                print('Second forward segment', flush=True)
                self.forward()
            self.pause(10.)
            print('Sequence completed according to Odom feedback.', flush=True)
        finally:
            self.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--turn-only', action='store_true')
    parser.add_argument('--distance', type=float, default=1.)
    parser.add_argument('--turn-deg', type=float, default=-90.)
    parser.add_argument('--linear-speed', type=float, default=.045)
    parser.add_argument('--turn-speed', type=float, default=.15)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not (0 < args.distance <= 1.5 and 0 < args.linear_speed <= .05 and
            .05 <= args.turn_speed <= .2 and 5 <= abs(args.turn_deg) <= 120):
        parser.error('Require distance (0,1.5] m, linear speed (0,0.05], turn speed [0.05,0.2], |angle| [5,120] deg')
    plan = 'turn only' if args.turn_only else 'forward %.2f m, turn, forward %.2f m' % (args.distance, args.distance)
    print('Plan: %s; turn %+.1f deg; speeds %.3f m/s, %.3f rad/s' %
          (plan, args.turn_deg, args.linear_speed, args.turn_speed), flush=True)
    if not args.execute:
        print('DRY RUN: no ROS initialization or velocity commands. Add --execute to run on Car2.')
        return
    import rospy
    rospy.init_node('car2_relative_motion', anonymous=True)
    if rospy.get_param('/use_sim_time', False):
        raise RuntimeError('Physical robot execution requires use_sim_time=false')
    controller = Controller(args)
    controller.run()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted; stop requested.')
        raise SystemExit(130)
    except Exception as error:
        print('ABORTED: %s' % error)
        raise SystemExit(1)
