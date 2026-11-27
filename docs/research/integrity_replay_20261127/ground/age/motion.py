"""Motion allowance for the simulated wheel displacement and last-packet age."""
import math
from scipy.stats import norm

STEP = .05
REF = 20
V_BASE = .12
OMEGA = .10
HEADING_SD = math.radians(2)
MOTION_RISK = .001

def motion_margin(n, k, age, lever, displacement, sigma_xy, sigma_yaw):
    """Simultaneous envelope on odometric displacement error, per simulated rover/run.

    The 63 possible integer source epochs each have at most 41 packet endpoints
    within their expiry. One union bound covers adaptive choice of center/packet.
    The limiting speed, including rotation of the lever arm, bounds missing age.
    """
    assert n >= 0 and 0 <= age <= STEP + 1e-10 and k >= REF
    if n == 0:
        return (V_BASE+lever*OMEGA)*age
    intervals = 63*41
    dt = n * STEP
    rayleigh = math.sqrt(2*math.log(3*intervals/MOTION_RISK))
    yaw_global = min(2., GLOBAL_Z*math.sqrt(HEADING_SD**2+(k-REF)*sigma_yaw**2))
    yaw_local = min(2., LOCAL_Z*math.sqrt(n)*sigma_yaw)
    translation = V_BASE*dt*yaw_global + rayleigh*sigma_xy*math.sqrt(n)
    rotation = lever*(yaw_global*min(2., OMEGA*dt)+yaw_local)
    max_antenna_speed = V_BASE+lever*OMEGA
    bound = translation + rotation + max_antenna_speed*age
    return min(bound, displacement+max_antenna_speed*(dt+age))


GLOBAL_Z = norm.isf(MOTION_RISK / (6*(1281-REF)))
LOCAL_Z = norm.isf(MOTION_RISK / (6*63*41))
