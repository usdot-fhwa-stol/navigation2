#! /usr/bin/env python3
# Copyright 2023 Samsung Research
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import math
import sys
import time

from typing import Optional

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Pose
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import PoseWithCovarianceStamped
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import ComputeRoute, ComputeAndTrackRoute
from nav2_msgs.srv import ManageLifecycleNodes

import rclpy

from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSReliabilityPolicy
from rclpy.qos import QoSProfile


class RouteTester(Node):

    def __init__(self, initial_pose: Pose, goal_pose: Pose, namespace: str = ''):
        super().__init__(node_name='nav2_tester', namespace=namespace)
        self.initial_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, 'initialpose', 10
        )

        pose_qos = QoSProfile(
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self.model_pose_sub = self.create_subscription(
            PoseWithCovarianceStamped, 'amcl_pose', self.poseCallback, pose_qos
        )
        self.initial_pose_received = False
        self.initial_pose = initial_pose
        self.goal_pose = goal_pose
        self.compute_action_client = ActionClient(self, ComputeRoute, 'compute_route')
        self.compute_track_action_client = ActionClient(self, ComputeAndTrackRoute, 'compute_and_track_route')
        self.feedback_msgs = []

    def runComputeRouteTest(self):
        # Test 1: See if we can compute a route that is valid and correctly sized
        self.info_msg("Waiting for 'ComputeRoute' action server")
        while not self.compute_action_client.wait_for_server(timeout_sec=1.0):
            self.info_msg("'ComputeRoute' action server not available, waiting...")

        route_msg = ComputeRoute.Goal()
        route_msg.start = self.getStampedPoseMsg(self.initial_pose)
        route_msg.goal = self.getStampedPoseMsg(self.goal_pose)
        route_msg.use_start = True
        route_msg.use_poses = True

        self.info_msg('Sending ComputeRoute goal request...')
        send_goal_future = self.compute_track_action_client.send_goal_async(goal_msg)

        rclpy.spin_until_future_complete(self, send_goal_future)
        goal_handle = send_goal_future.result()

        if not goal_handle.accepted:
            self.error_msg('Goal rejected')
            return False

        self.info_msg('Goal accepted')
        get_result_future = goal_handle.get_result_async()

        self.info_msg("Waiting for 'ComputeRoute' action to complete")
        rclpy.spin_until_future_complete(self, get_result_future)
        status = get_result_future.result().status
        result = get_result_future.result().result
        if status != GoalStatus.STATUS_SUCCEEDED:
            self.info_msg(f'Goal failed with status code: {status}')
            return False

        self.info_msg('Action completed! Checking validity of results...')

        # Check result for validity
        assert(len(result.path) > 0)
        assert(result.route.route_cost > 0) # TODO for actual values expected
        assert(len(result.route.nodes) > 0) # TODO for actual values expected
        assert(len(result.route.edge_ids) > 0) # TODO for actual values expected
        assert(result.error_code == 0)

        self.info_msg('Goal succeeded!')
        return True

    def runTrackRouteTest(self):
        # Test 1: See if we can compute and track a route with proper state
        self.info_msg("Waiting for 'ComputeAndTrackRoute' action server")
        while not self.compute_track_action_client.wait_for_server(timeout_sec=1.0):
            self.info_msg("'ComputeAndTrackRoute' action server not available, waiting...")

        route_msg = ComputeAndTrackRoute.Goal()
        route_msg.goal = self.getStampedPoseMsg(self.goal_pose)
        route_msg.use_start = False  # Use TF pose instead
        route_msg.use_poses = True

        self.info_msg('Sending ComputeAndTrackRoute goal request...')
        send_goal_future = self.compute_track_action_client.send_goal_async(
            goal_msg, feedback_callback=self.feedback_callback)

        rclpy.spin_until_future_complete(self, send_goal_future)
        goal_handle = send_goal_future.result()

        if not goal_handle.accepted:
            self.error_msg('Goal rejected')
            return False

        self.info_msg('Goal accepted')
        get_result_future = goal_handle.get_result_async()

        self.info_msg("Waiting for 'ComputeAndTrackRoute' action to complete")
        progressing = True
        last_feedback_msg = None
        while progressing:
            rclpy.spin_until_future_complete(self, get_result_future, timeout_sec = 0.10)
            status = get_result_future.result().status
            if status == GoalStatus.STATUS_SUCCEEDED:
                progressing = False
            elif status == GoalStatus.STATUS_CANCELED or status == GoalStatus.STATUS_ABORTED:
                self.info_msg(f'Goal failed with status code: {status}')
                return False

            # Else, processing. Check feedback
            while len(self.feedback_msgs) > 0:
                feedback_msg = self.feedback_msgs.pop(0)
                assert(len(feedback_msg.path) > 0)
                assert(feedback_msg.route.route_cost > 0) # TODO for actual values expected
                assert(len(feedback_msg.route.nodes) > 0) # TODO for actual values expected
                assert(len(feedback_msg.route.edge_ids) > 0) # TODO for actual values expected
                assert(len(feedback_msg.operations_triggered) == 1)
                assert(feedback_msg.operations_triggered[0] == "ReroutingService")

                if last_feedback_msg and last_feedback_msg != feedback_msg and last_feedback_msg.route == False:
                    if last_feedback_msg.next_node_id != feedback_msg.last_node_id:
                        self.error_msg('Feedback state is not tracking in order!')
                        return False
                    if feedback_msg.current_edge_id == 0:
                        self.error_msg('Feedback state does not contain the proper edge info!')
                        return False

                last_feedback_msg = feedback_msg

        result = get_result_future.result().result

        if int(last_feedback_msg.next_node_id) != int(last_feedback.route.nodes[-1].nodeid):
            self.error_msg('Terminal feedback state is not correct!')
            return False

        self.info_msg('Action completed! Checking validity of terminal condition...')

        # Check result for validity
        if not self.distanceFromGoal() < 0.5:
            self.error_msg('Did not make it to the goal pose!')
            return False

        self.info_msg('Goal succeeded!')
        return True

    def feedback_callback(self, feedback_msg):
        self.feedback_msgs.append(feedback_msg)

    def distanceFromGoal(self):
        d_x = self.current_pose.position.x - self.goal_pose.position.x
        d_y = self.current_pose.position.y - self.goal_pose.position.y
        distance = math.sqrt(d_x * d_x + d_y * d_y)
        self.info_msg(f'Distance from goal is: {distance}')
        return distance

    def info_msg(self, msg: str):
        self.get_logger().info('\033[1;37;44m' + msg + '\033[0m')

    def error_msg(self, msg: str):
        self.get_logger().error('\033[1;37;41m' + msg + '\033[0m')

    def setInitialPose(self):
        msg = PoseWithCovarianceStamped()
        msg.pose.pose = self.initial_pose
        msg.header.frame_id = 'map'
        self.info_msg('Publishing Initial Pose')
        self.initial_pose_pub.publish(msg)
        self.currentPose = self.initial_pose

    def getStampedPoseMsg(self, pose: Pose):
        msg = PoseStamped()
        msg.header.frame_id = 'map'
        msg.pose = pose
        return msg

    def poseCallback(self, msg):
        self.info_msg('Received amcl_pose')
        self.current_pose = msg.pose.pose
        self.initial_pose_received = True

    def wait_for_node_active(self, node_name: str):
        # Waits for the node within the tester namespace to become active
        self.info_msg(f'Waiting for {node_name} to become active')
        node_service = f'{node_name}/get_state'
        state_client = self.create_client(GetState, node_service)
        while not state_client.wait_for_service(timeout_sec=1.0):
            self.info_msg(f'{node_service} service not available, waiting...')
        req = GetState.Request()  # empty request
        state = 'UNKNOWN'
        while state != 'active':
            self.info_msg(f'Getting {node_name} state...')
            future = state_client.call_async(req)
            rclpy.spin_until_future_complete(self, future)
            if future.result() is not None:
                state = future.result().current_state.label
                self.info_msg(f'Result of get_state: {state}')
            else:
                self.error_msg(
                    f'Exception while calling service: {future.exception()!r}'
                )
            time.sleep(5)

    def shutdown(self):
        self.info_msg('Shutting down')
        self.action_client.destroy()

        transition_service = 'lifecycle_manager_navigation/manage_nodes'
        mgr_client = self.create_client(ManageLifecycleNodes, transition_service)
        while not mgr_client.wait_for_service(timeout_sec=1.0):
            self.info_msg(f'{transition_service} service not available, waiting...')

        req = ManageLifecycleNodes.Request()
        req.command = ManageLifecycleNodes.Request().SHUTDOWN
        future = mgr_client.call_async(req)
        try:
            self.info_msg('Shutting down navigation lifecycle manager...')
            rclpy.spin_until_future_complete(self, future)
            future.result()
            self.info_msg('Shutting down navigation lifecycle manager complete.')
        except Exception as e:  # noqa: B902
            self.error_msg(f'Service call failed {e!r}')
        transition_service = 'lifecycle_manager_localization/manage_nodes'
        mgr_client = self.create_client(ManageLifecycleNodes, transition_service)
        while not mgr_client.wait_for_service(timeout_sec=1.0):
            self.info_msg(f'{transition_service} service not available, waiting...')

        req = ManageLifecycleNodes.Request()
        req.command = ManageLifecycleNodes.Request().SHUTDOWN
        future = mgr_client.call_async(req)
        try:
            self.info_msg('Shutting down localization lifecycle manager...')
            rclpy.spin_until_future_complete(self, future)
            future.result()
            self.info_msg('Shutting down localization lifecycle manager complete')
        except Exception as e:  # noqa: B902
            self.error_msg(f'Service call failed {e!r}')

    def wait_for_initial_pose(self):
        self.initial_pose_received = False
        while not self.initial_pose_received:
            self.info_msg('Setting initial pose')
            self.setInitialPose()
            self.info_msg('Waiting for amcl_pose to be received')
            rclpy.spin_once(self, timeout_sec=1)


def run_all_tests(robot_tester):
    # set transforms to use_sim_time
    robot_tester.wait_for_node_active('amcl')
    robot_tester.wait_for_initial_pose()
    robot_tester.wait_for_node_active('bt_navigator')
    result = robot_tester.runComputeRouteTest()
    result = result and robot_tester.runTrackRouteTest()

    if result:
        robot_tester.info_msg('Test PASSED')
    else:
        robot_tester.error_msg('Test FAILED')
    return result


def fwd_pose(x=0.0, y=0.0, z=0.01):
    initial_pose = Pose()
    initial_pose.position.x = x
    initial_pose.position.y = y
    initial_pose.position.z = z
    initial_pose.orientation.x = 0.0
    initial_pose.orientation.y = 0.0
    initial_pose.orientation.z = 0.0
    initial_pose.orientation.w = 1.0
    return initial_pose


def main(argv=sys.argv[1:]):
    # The robot(s) positions from the input arguments
    parser = argparse.ArgumentParser(description='Route server tester node')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '-r',
        '--robot',
        action='append',
        nargs=4,
        metavar=('init_x', 'init_y', 'final_x', 'final_y'),
        help='The robot starting and final positions.',
    )
    args, unknown = parser.parse_known_args()

    rclpy.init()

    # Create test object
    init_x, init_y, final_x, final_y = args.robot[0]
    tester = RouteTester(
        initial_pose=fwd_pose(float(init_x), float(init_y)),
        goal_pose=fwd_pose(float(final_x), float(final_y)),
    )
    tester.info_msg(
        'Starting tester, robot going from '
        + init_x
        + ', '
        + init_y
        + ' to '
        + final_x
        + ', '
        + final_y
        + ' via route server.'
    )

    # wait a few seconds to make sure entire stacks are up
    time.sleep(10)

    # run tests
    passed = run_all_tests(tester)

    tester.shutdown()
    testers[0].info_msg('Done Shutting Down.')

    if passed != expect_failure:
        testers[0].info_msg('Exiting failed')
        exit(1)
    else:
        testers[0].info_msg('Exiting passed')
        exit(0)


if __name__ == '__main__':
    main()
