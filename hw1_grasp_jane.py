#!/usr/bin/env python

PACKAGE_NAME = 'hw1'

# Standard Python Imports
import os
import copy
import time
import math
import numpy as np
np.random.seed(0)
import scipy

# OpenRAVE
import openravepy
#openravepy.RaveInitialize(True, openravepy.DebugLevel.Debug)


curr_path = os.getcwd()
relative_ordata = '/models'
ordata_path_thispack = curr_path + relative_ordata


#this sets up the OPENRAVE_DATA environment variable to include the files we're using
openrave_data_path = os.getenv('OPENRAVE_DATA', '')
openrave_data_paths = openrave_data_path.split(':')
if ordata_path_thispack not in openrave_data_paths:
  if openrave_data_path == '':
      os.environ['OPENRAVE_DATA'] = ordata_path_thispack
  else:
      datastr = str('%s:%s'%(ordata_path_thispack, openrave_data_path))
      os.environ['OPENRAVE_DATA'] = datastr

#set database file to be in this folder only
relative_ordatabase = '/database'
ordatabase_path_thispack = curr_path + relative_ordatabase
os.environ['OPENRAVE_DATABASE'] = ordatabase_path_thispack # set path: environment variable 

#get rid of warnings
openravepy.RaveInitialize(True, openravepy.DebugLevel.Fatal)
openravepy.misc.InitOpenRAVELogging()

def normalize(n, range):
  return (1.0*n - range[0])/(range[1] - range[0])

class RoboHandler:
  def __init__(self):
    print "Initializing..."
    print "Openrave..."
    self.openrave_init()
    print "Problem..."
    self.problem_init()

    #order grasps based on your own scoring metric
    print "Ordering grasps..."
    self.order_grasps()

    #order grasps with noise
    print "Ordering with noise..."
    #self.order_grasps_noisy()

  # the usual initialization for openrave
  def openrave_init(self):
    self.env = openravepy.Environment()
    self.env.SetViewer('qtcoin')
    self.env.GetViewer().SetName('HW1 Viewer')
    self.env.Load('models/%s.env.xml' %PACKAGE_NAME)
    
    # time.sleep(3) # wait for viewer to initialize. May be helpful to uncomment
    self.robot = self.env.GetRobots()[0]
    self.manip = self.robot.GetActiveManipulator()
    self.end_effector = self.manip.GetEndEffector()

    self.s = [0, 0] # singmaMin range
    self.v = [0, 0] # volumeG range
    self.i = [0, 0] # isotropy range
    self.raw_scores = []

    # cc = openravepy.RaveCreateCollisionChecker(self.env, 'pqp')
    # self.env.SetCollisionChecker(cc)

  # problem specific initialization - load target and grasp module
  def problem_init(self):
    self.target_kinbody = self.env.ReadKinBodyURI('models/objects/champagne.iv')
    #self.target_kinbody = self.env.ReadKinBodyURI('models/objects/winegoblet.iv')
    #self.target_kinbody = self.env.ReadKinBodyURI('models/objects/black_plastic_mug.iv')

    #change the location so it's not under the robot
    T = self.target_kinbody.GetTransform()
    T[0:3,3] += np.array([0.5, 0.5, 0.5])
    self.target_kinbody.SetTransform(T)
    self.env.AddKinBody(self.target_kinbody)

    # create a grasping module
    self.gmodel = openravepy.databases.grasping.GraspingModel(self.robot, self.target_kinbody)

    # if you want to set options, e.g. friction
    options = openravepy.options
    options.friction = 0.1
    if not self.gmodel.load():
      self.gmodel.autogenerate(options)

    self.graspindices = self.gmodel.graspindices
    self.grasps = self.gmodel.grasps

  def get_raw_score_range(self):
    # go this loop to get raw scores and find the range of the raw scores
    for grasp in self.grasps_ordered:
      self.raw_scores.append(self.eval_grasp(grasp))

    # get the range of the three metric through the whole loop doing evaluation for each grasp
    all_sigmaMin = [n[0] for n in self.raw_scores]
    all_volumnG = [n[1] for n in self.raw_scores]
    all_isotropy = [n[2] for n in self.raw_scores]
    self.s = [min(all_sigmaMin), max(all_sigmaMin)]
    self.v = [min(all_volumnG), max(all_volumnG)]
    self.i = [min(all_isotropy), max(all_isotropy)]

  
  # order the grasps - call eval grasp on each, set the 'performance' index, and sort
  def order_grasps(self):
    self.grasps_ordered = self.grasps.copy() #you should change the order of self.grasps_ordered
    
    # get raw scores before sorting
    self.get_raw_score_range()

    # normalize raw scores and linearly combine them to get the final score for each grasp
    # This cannot be done in eval() function because the run-time eval() doesn't have those ranges to normalize the metrics until all grasps are evaluated.
    for i, grasp in enumerate(self.grasps_ordered):
      sigmaMin = self.raw_scores[i][0]
      volumeG = self.raw_scores[i][1]
      isotropy = self.raw_scores[i][2]
      score = 2.0*normalize(sigmaMin, self.s) + 5.0*normalize(volumeG, self.v) + 10.0*normalize(isotropy, self.i)
      grasp[self.graspindices.get('performance')] = score
    
    # sort!
    order = np.argsort(self.grasps_ordered[:,self.graspindices.get('performance')[0]])
    order = order[::-1]
    self.grasps_ordered = self.grasps_ordered[order]

  
  # order the grasps - but instead of evaluating the grasp, evaluate random perturbations of the grasp
  def order_grasps_noisy(self):
    self.grasps_ordered_noisy = self.grasps_ordered.copy() #you should change the order of self.grasps_ordered_noisy
    #TODO set the score with your evaluation function (over random samples) and sort
    num_noisy_samples = 5
  

    for grasp in self.grasps_ordered_noisy:
      noisy_samples = []
      for i in range(num_noisy_samples):
        noisy_grasp = self.sample_random_grasp(grasp)
        score = self.eval_grasp(noisy_grasp)
        noisy_samples.append(score)

      grasp[self.graspindices.get('performance')] = sum(noisy_samples) / num_noisy_samples

    # sort!
    order = np.argsort(self.grasps_ordered_noisy[:,self.graspindices.get('performance')[0]])
    order = order[::-1]
    self.grasps_ordered_noisy = self.grasps_ordered_noisy[order]



  # function to evaluate grasps
  # returns a score, which is some metric of the grasp
  # higher score should be a better grasp
  def eval_grasp(self, grasp):
    with self.robot:
      #contacts is a 2d array, where contacts[i,0-2] are the positions of contact i and contacts[i,3-5] is the direction
      try:
        contacts,finalconfig,mindist,volume = self.gmodel.testGrasp(grasp=grasp,translate=True,forceclosure=False)

        obj_position = self.gmodel.target.GetTransform()[0:3,3]
        # for each contact
        G = np.zeros(shape=(6, len(contacts))) #the wrench matrix
        wrench = np.zeros(shape=(6,1))
        for i, c in enumerate(contacts):
          pos = c[0:3] - obj_position
          dir = -c[3:] #this is already a unit vector
          
          # fill G
          torque = np.cross(pos, dir)
          wrench = np.concatenate([dir, torque])

          G[:, i] = wrench
        
        # Use SVD to compute minimum score
        U, S, V = np.linalg.svd(G)
        sigmaMin = abs(S[-1])
        sigmaMax = abs(S[0])
        volumeG = np.linalg.det(np.dot(G, np.transpose(G))) ** 0.5
        isotropy = abs(float(sigmaMin) / sigmaMax)

        score = [sigmaMin, volumeG, isotropy]
        return score
      except openravepy.planning_error,e:
        #you get here if there is a failure in planning
        #example: if the hand is already intersecting the object at the initial position/orientation
        return [0.00, 0.00, 0.00]# TODO you may want to change this
      
      #heres an interface in case you want to manipulate things more specifically
      #NOTE for this assignment, your solutions cannot make use of graspingnoise
# self.robot.SetTransform(np.eye(4)) # have to reset transform in order to remove randomness
# self.robot.SetDOFValues(grasp[self.graspindices.get('igrasppreshape')], self.manip.GetGripperIndices())
# self.robot.SetActiveDOFs(self.manip.GetGripperIndices(), self.robot.DOFAffine.X + self.robot.DOFAffine.Y + self.robot.DOFAffine.Z)
# self.gmodel.grasper = openravepy.interfaces.Grasper(self.robot, friction=self.gmodel.grasper.friction, avoidlinks=[], plannername=None)
# contacts, finalconfig, mindist, volume = self.gmodel.grasper.Grasp( \
# direction = grasp[self.graspindices.get('igraspdir')], \
# roll = grasp[self.graspindices.get('igrasproll')], \
# position = grasp[self.graspindices.get('igrasppos')], \
# standoff = grasp[self.graspindices.get('igraspstandoff')], \
# manipulatordirection = grasp[self.graspindices.get('imanipulatordirection')], \
# target = self.target_kinbody, \
# graspingnoise = 0.0, \
# forceclosure = True, \
# execute = False, \
# outputfinal = True, \
# translationstepmult = None, \
# finestep = None )



  # given grasp_in, create a new grasp which is altered randomly
  # you can see the current position and direction of the grasp by:
  # grasp[self.graspindices.get('igrasppos')]
  # grasp[self.graspindices.get('igraspdir')]
  def sample_random_grasp(self, grasp_in):
    grasp = grasp_in.copy()

    #sample random position
    RAND_DIST_SIGMA = 0.01 #TODO you may want to change this
    pos_orig = grasp[self.graspindices['igrasppos']]

    pos_noise = pos_orig + np.random.normal(loc=0.0, scale=RAND_DIST_SIGMA)

    #TODO set a random position -- DONE
    grasp[self.graspindices['igrasppos']] = pos_noise

    #sample random orientation
    RAND_ANGLE_SIGMA = np.pi/24 #TODO you may want to change this
    dir_orig = grasp[self.graspindices['igraspdir']]
    roll_orig = grasp[self.graspindices['igrasproll']]

    #TODO set the direction and roll to be random -- DONE
    dir_noise = dir_orig + np.random.normal(loc=0.0, scale=RAND_ANGLE_SIGMA)
    roll_noise = roll_orig + np.random.normal(loc=0.0, scale=RAND_ANGLE_SIGMA)

    grasp[self.graspindices['igraspdir']]  = dir_noise
    grasp[self.graspindices['igrasproll']] = roll_noise

    return grasp


  #displays the grasp
  def show_grasp(self, grasp, delay=1.5):
    with openravepy.RobotStateSaver(self.gmodel.robot):
      with self.gmodel.GripperVisibility(self.gmodel.manip):
        time.sleep(0.1) # let viewer update?
        try:
          with self.env:
            contacts,finalconfig,mindist,volume = self.gmodel.testGrasp(grasp=grasp,translate=True,forceclosure=True)
            #if mindist == 0:
            # print 'grasp is not in force closure!'
            contactgraph = self.gmodel.drawContacts(contacts) if len(contacts) > 0 else None
            self.gmodel.robot.GetController().Reset(0)
            self.gmodel.robot.SetDOFValues(finalconfig[0])
            self.gmodel.robot.SetTransform(finalconfig[1])
            self.env.UpdatePublishedBodies()
            time.sleep(delay)
        except openravepy.planning_error,e:
          print 'bad grasp!',e

if __name__ == '__main__':
  robo = RoboHandler()

  delay = 20
  for i in range(4):
    print 'Showing grasp ', i
    robo.show_grasp(robo.grasps_ordered[i], delay=delay)
        

  # import IPython
  # IPython.embed()
  # print "Showing grasps..."
  # for grasp in robo.grasps_ordered:
  # robo.show_grasp(grasp)
  # time.sleep(10000) #to keep the openrave window open