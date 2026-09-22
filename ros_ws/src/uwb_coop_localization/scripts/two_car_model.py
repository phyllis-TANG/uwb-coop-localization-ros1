#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""ROS-independent motion and ranging helpers for the two-car simulator."""

from __future__ import division

import math


class Pose2D(object):
    def __init__(self, x, y, yaw):
        self.x = float(x)
        self.y = float(y)
        self.yaw = float(yaw)


def wrap_angle(angle):
    """Wrap an angle to [-pi, pi)."""
    return (float(angle) + math.pi) % (2.0 * math.pi) - math.pi


def advance_unicycle(pose, linear_velocity, angular_velocity, dt):
    """Advance a planar unicycle state with a midpoint heading step."""
    dt = float(dt)
    if dt < 0.0:
        raise ValueError("dt must be non-negative")

    linear_velocity = float(linear_velocity)
    angular_velocity = float(angular_velocity)
    midpoint_yaw = pose.yaw + 0.5 * angular_velocity * dt

    return Pose2D(
        pose.x + linear_velocity * math.cos(midpoint_yaw) * dt,
        pose.y + linear_velocity * math.sin(midpoint_yaw) * dt,
        wrap_angle(pose.yaw + angular_velocity * dt),
    )


def planar_distance(first, second):
    """Return the Euclidean distance between two planar poses."""
    return math.hypot(second.x - first.x, second.y - first.y)


def validate_probability(value, name):
    value = float(value)
    if value < 0.0 or value > 1.0:
        raise ValueError("%s must be in [0.0, 1.0]" % name)
    return value


def sample_range(
        true_distance,
        random_generator,
        noise_stddev=0.0,
        bias=0.0,
        nlos_probability=0.0,
        nlos_bias=0.0,
        dropout_probability=0.0):
    """Sample one range and return ``(value, quality, is_nlos)``.

    ``None`` is returned for a simulated dropout.  NLOS is deliberately a
    configurable positive bias rather than a universal correction model.
    """
    noise_stddev = float(noise_stddev)
    if noise_stddev < 0.0:
        raise ValueError("noise_stddev must be non-negative")

    nlos_probability = validate_probability(
        nlos_probability,
        "nlos_probability",
    )
    dropout_probability = validate_probability(
        dropout_probability,
        "dropout_probability",
    )

    if random_generator.random() < dropout_probability:
        return None

    is_nlos = random_generator.random() < nlos_probability
    measurement = float(true_distance) + float(bias)
    if is_nlos:
        measurement += float(nlos_bias)
    if noise_stddev:
        measurement += random_generator.gauss(0.0, noise_stddev)

    # Quality is only a simulator label.  Real Frame3 quality remains unknown.
    quality = 0.0 if is_nlos else 1.0
    return max(0.0, measurement), quality, is_nlos
