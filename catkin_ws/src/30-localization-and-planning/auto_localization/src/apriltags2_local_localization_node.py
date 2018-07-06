#!/usr/bin/env python
import rospkg
import rospy
import yaml
import socket
from duckietown_msgs.msg import TagInfo, BoolStamped, RemapPose, RemapPoseArray
from apriltags2_ros.msg import AprilTagDetectionArray, AprilTagDetection
import numpy as np
import tf
# from tf
import tf.transformations as tr
from geometry_msgs.msg import PoseStamped


# This node localizes Apriltags prior defined in
# Coordinates will be given in
# Subscribes:   Apriltag detections (tf)
# Publishes:    Coordinates of BotAprilTag in Reference to FixedTags as tf_message

class AprilLocalLocalization(object):
    """ """
    def __init__(self):
        """ """
        self.node_name = "apriltags2_local_localization_node"

        # Constants
        self.world_frame = "world"
        self.camera_frame = "camera"
        self.duckiebot_frame = "duckiebot"

        # Number of fixed AprilTags detected in the field of view
        self.fixed_tags_number = 0

        # This dictionary contains information of the fixed tags
        # {TagID : [Type | detection.pose]}
        self.fixed_tags_dict = dict()
        # Setup the publishers and subscribers from localization_node
        # self.sub_april = rospy.Subscriber("~apriltags", AprilTagsWithInfos, self.tag_callback)
        # self.pub_tf = rospy.Publisher("/tf", TFMessage, queue_size=1, latch=True)


# -------- Start adding back the tag info stuff
# Code from apriltags_postprocessing_node

        rospack = rospkg.RosPack()
        self.pkg_path = rospack.get_path('apriltags_ros')
        tags_filepath = self.setupParam("~tags_file", self.pkg_path+"/../signs_and_tags/apriltagsDB.yaml") # No tags_file input atm., so default value is used
        self.loc = self.setupParam("~loc", -1) # -1 if no location is given
        tags_file = open(tags_filepath, 'r')
        self.tags_dict = yaml.load(tags_file)
        tags_file.close()
        self.info = TagInfo()

        self.sign_types = {"StreetName": self.info.S_NAME,
            "TrafficSign": self.info.SIGN,
            "Light": self.info.LIGHT,
            "Localization": self.info.LOCALIZE,
            "Vehicle": self.info.VEHICLE}

# ---- end tag info stuff


        self.sub_prePros        = rospy.Subscriber("apriltags_in", AprilTagDetectionArray, self.callback, queue_size=1)
        self.sub_tf             = tf.TransformListener()
        self.pub_tf = tf.TransformBroadcaster()
        #self.pub_postPros       = rospy.Publisher("~apriltags_out", AprilTagsWithInfos, queue_size=1)
        self.pub_postPros = rospy.Publisher("~apriltags_out", RemapPoseArray, queue_size=1)
        # self.pub_visualize      = rospy.Publisher("~tag_pose", PoseStamped, queue_size=1)

        rospy.loginfo("[%s] has started", self.node_name)



    def setupParam(self,param_name,default_value):
        value = rospy.get_param(param_name,default_value)
        rospy.set_param(param_name,value) #Write to parameter server for transparancy
        rospy.loginfo("[%s] %s = %s " %(self.node_name,param_name,value))
        return value

    def callback(self, msg):
        tag_infos = []
        remap_poses_array = RemapPoseArray()

        # Load tag detections message
        for detection in msg.detections:

            # rospy.loginfo("[%s] detection", self.node_name)
            # ------ start tag info processing

            new_info = TagInfo()
            new_info.id = int(detection.id[0])
            id_info = self.tags_dict[new_info.id]



            # Check yaml file to fill in ID-specific information

            new_info.tag_type = self.sign_types[id_info['tag_type']]

            # fixed tags will be added to the database,
            # StreetSigns, TrafficSigns are considered to be fixed tags
            if (new_info.tag_type == self.info.S_NAME) or (new_info.tag_type == self.info.SIGN):
                 # add fixed tag to the database, overwrite old information
                 self.fixed_tags_dict[new_info.id] = [new_info.tag_type, detection.pose]
                 # for fixed_frame in self.fixed_tags_dict:
                 #    rospy.loginfo("FixedFrame: %s",fixed_frame)



            # perform coordinate transform for moving tags
            #    in reference to the fixed tags
            elif new_info.tag_type == self.info.VEHICLE:
                new_info.vehicle_name = id_info['vehicle_name']
                #rospy.loginfo("Detected %s with Tag ID %s", new_info.vehicle_name, new_info.id)
                # cantrans = tf.canTransform('quacky/color_optical_frame', 'Tag15', now)


                # Coordinates transform for each fixed frame
                for fixed_frame in self.fixed_tags_dict:
                    remap_pose = RemapPose()

                    #  in terminal it would be rosrun tf tf_echo fixed_frame bot_frame
                    # how about the time?? rospy.time(0) probably induces an artificial delay
                    try:
                        # Switch the position of look up transform
                        # Set parent frame to Duckiebot frame, child frame to fixed frame (tag)
                        # Since we want the transform from Duckiebot to fixed frame (tag)
                        (trans,rot) = self.sub_tf.lookupTransform('Tag'+str(fixed_frame), 'Tag'+str(new_info.id), rospy.Time(0))
                        #trans = [0, 0, 0]
                        #rot = [0, 0, 0, 1]
                    except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException):
                        continue

                    # Publish this as a tf message TODO: maybe an new unique topic would be more useful here?
                    self.pub_tf.sendTransform(trans,
                                              rot,
                                              rospy.Time.now(),
                                              new_info.vehicle_name,
                                              'Tag'+str(fixed_frame))

                    #Add data to remap pose message
                    remap_pose.host = socket.gethostname()
                    remap_pose.frame_id = fixed_frame
                    remap_pose.bot_id = new_info.id
                    remap_pose.posestamped.header.stamp = detection.pose.header.stamp
                    remap_pose.posestamped.pose.position.x = trans[0]
                    remap_pose.posestamped.pose.position.y = trans[1]
                    remap_pose.posestamped.pose.position.z = trans[2]
                    remap_pose.posestamped.pose.orientation.x = rot[0]
                    remap_pose.posestamped.pose.orientation.y = rot[1]
                    remap_pose.posestamped.pose.orientation.z = rot[2]
                    remap_pose.posestamped.pose.orientation.w = rot[3]
                    #Add this remap pose to the array
                    remap_poses_array.poses.append(remap_pose)

                    # Debugging Output (comment that to optimiza the code)
                    '''
                    rot_euler = tf.transformations.euler_from_quaternion(rot)
                    rot_euler = [elem * 360 / (2 *3.14159) for elem in rot_euler]
                    trans_rnd = ['%.3f' % elem for elem in trans]
                    rot_rnd   = ['%.1f' % elem for elem in rot_euler]
                    rospy.loginfo("%s In reference to Tag%s: \nTranslation: %s \nOrientation: %s \n",
                                   new_info.vehicle_name, fixed_frame, trans_rnd, rot_rnd)
                    '''

        self.pub_postPros.publish(remap_poses_array)


        #     tag_infos.append(new_info)
        #     # --- end tag info processing
        #
        # new_tag_data = AprilTagsWithInfos()
        # new_tag_data.detections = msg.detections
        # new_tag_data.infos = tag_infos
        # # Publish Message
        # self.pub_postPros.publish(new_tag_data)

if __name__ == '__main__':
    rospy.init_node('AprilLocalLocalization',anonymous=False)
    node = AprilLocalLocalization()
    rospy.spin()
