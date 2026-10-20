"""Hardware-free checks of the two-car factor graph and lever-arm geometry."""
import unittest

import numpy as np

import two_car_offline_graph as model


class TwoCarGraphTests(unittest.TestCase):
    def test_odom_body_increments_ignore_odom_origin_and_global_heading(self):
        local = np.array([[0., 0., 0.], [1., 0., 0.],
                          [1., 1., np.pi/2], [1., 2., np.pi/2]])
        reference_body, reference_yaw = model.odom_between(local)
        angle = 0.73
        transformed = local.copy()
        transformed[:, :2] = local[:, :2]@model.rot(angle).T + [5., -2.]
        transformed[:, 2] += angle
        body, turn = model.odom_between(transformed)
        np.testing.assert_allclose(body, reference_body, atol=1e-12)
        np.testing.assert_allclose(turn, reference_yaw, atol=1e-12)

    def test_rotated_antenna_offset(self):
        base = np.array([[1., 2., np.pi/2]])
        np.testing.assert_allclose(model.antenna(base, [0.12, -0.08]),
                                   [[1.08, 2.12]], atol=1e-12)

    def test_peer_factor_is_one_per_keyframe_and_only_joint_changes(self):
        n = 6
        times = np.arange(1., n+1.)
        anchors = {'node_2': [5.28, 5.16, 2.755],
                   'node_3': [5.28, 2.86, 2.355],
                   'node_8': [0.10, 2.41, 2.30],
                   'node_10': [3.26, 0.10, 2.355]}
        scenario = model.scenarios('L')['primary']
        cars = {}
        truth = {}
        for car in ('car1', 'car2'):
            heading = np.radians(model.HEADING_DEG['L'][car])
            lever = model.LEVER[car]
            ant = np.array([model.START['L'][car] for _ in times], dtype=float)
            if car == 'car2':
                ant[:, 1] += np.linspace(0., 0.4, n)
            base = np.column_stack((ant-model.antenna(np.array([[0., 0., heading]]), lever)[0],
                                    np.full(n, heading)))
            observations = []
            for point in ant:
                observations.append({key: float(np.linalg.norm(
                    np.r_[point, model.HEIGHT[car]]-np.asarray(xyz)))
                                     for key, xyz in anchors.items()})
            cars[car] = {'local': base.copy(), 'heading': heading,
                         'lever': lever.copy(), 'initial': base.copy(),
                         'walls': observations}
            truth[car] = ant
        peer = [float(np.linalg.norm(np.r_[truth['car1'][i]-truth['car2'][i],
                                          model.HEIGHT['car1']-model.HEIGHT['car2']]))
                for i in range(n)]
        inputs = {'times': times, 'cars': cars, 'anchors': anchors,
                  'parameters': model.PARAM,
                  'scenario': scenario,
                  'peers': [{'range_m': x-0.2, 'directions_m': [x-0.2, x-0.2],
                             'direction_counts': [40, 40]} for x in peer]}
        independent = model.graph(inputs, joint=False)
        joint = model.graph(inputs, joint=True)
        self.assertEqual(independent['peer_factor_count'], 0)
        self.assertEqual(joint['peer_factor_count'], n)
        self.assertEqual(independent['wall_factor_count'], joint['wall_factor_count'])
        np.testing.assert_allclose(independent['antenna_xy'][0], truth['car1'], atol=1e-5)
        np.testing.assert_allclose(independent['antenna_xy'][1], truth['car2'], atol=1e-5)
        self.assertLess(np.median(np.abs(joint['peer_residual_m'])),
                        np.median(np.abs(independent['peer_residual_m'])))
        for entry in inputs['peers']:
            entry['range_m'] += 1.
        independent_with_different_peer = model.graph(inputs, joint=False)
        np.testing.assert_allclose(independent_with_different_peer['antenna_xy'],
                                   independent['antenna_xy'], atol=1e-7)


if __name__ == '__main__':
    unittest.main()
