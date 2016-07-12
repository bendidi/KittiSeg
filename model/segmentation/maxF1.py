#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Trains, evaluates and saves the model network using a queue."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import numpy as np
import scipy as scp
import random
from seg_utils import seg_utils as seg


import tensorflow as tf


def decoder(hypes, logits):
    """Apply decoder to the logits.

    Args:
      logits: Logits tensor, float - [batch_size, NUM_CLASSES].

    Return:
      logits: the logits are already decoded.
    """
    return logits


def loss(hypes, logits, labels):
    """Calculate the loss from the logits and the labels.

    Args:
      logits: Logits tensor, float - [batch_size, NUM_CLASSES].
      labels: Labels tensor, int32 - [batch_size].

    Returns:
      loss: Loss tensor of type float.
    """
    with tf.name_scope('loss'):
        logits = tf.reshape(logits, (-1, 2))
        shape = [logits.get_shape()[0], 2]
        epsilon = tf.constant(value=hypes['solver']['epsilon'])
        # logits = logits + epsilon
        la = tf.to_float(tf.reshape(labels, (-1, 2)))
        lg = tf.nn.softmax(logits)
        labels = tf.to_float(tf.reshape(labels, (-1, 2)))[:, 1]
        logits = tf.nn.softmax(logits)[:, 1]

        '''
        recall = totalTP / float( totalPosNum )
        precision =  totalTP / (totalTP + totalFP + 1e-10)
        F = (1 + betasq) * (precision * recall)/((betasq * precision)
                                                         + recall + 1e-10)
        '''

        true_positive = tf.reduce_sum(labels*logits)
        false_positive = tf.reduce_sum((1-labels)*logits)

        recall = true_positive / tf.reduce_sum(labels)
        precision = true_positive / (true_positive + false_positive + epsilon)

        score = 2*recall * precision / (precision + recall)
        f1_score = 1 - 2*recall * precision / (precision + recall)
        tf.add_to_collection('losses', f1_score)

        loss = tf.add_n(tf.get_collection('losses'), name='total_loss')
    return loss


def evaluation(hypes, logits, labels):
    """Evaluate the quality of the logits at predicting the label.

    Args:
      logits: Logits tensor, float - [batch_size, NUM_CLASSES].
      labels: Labels tensor, int32 - [batch_size], with values in the
        range [0, NUM_CLASSES).

    Returns:
      A scalar int32 tensor with the number of examples (out of batch_size)
      that were predicted correctly.
    """
    # For a classifier model, we can use the in_top_k Op.
    # It returns a bool tensor with shape [batch_size] that is true for
    # the examples where the label's is was in the top k (here k=1)
    # of all logits for that example.
    with tf.name_scope('eval'):

        num_classes = hypes['arch']['num_classes']

        logits = tf.reshape(logits, (-1, num_classes))
        shape = [logits.get_shape()[0], num_classes]
        epsilon = tf.constant(value=hypes['solver']['epsilon'])
        # logits = logits + epsilon
        labels = tf.to_float(tf.reshape(labels, (-1, num_classes)))

        logits = tf.nn.softmax(logits)

        intersection = tf.reduce_sum(labels*logits, reduction_indices=0)
        union = tf.reduce_sum(labels+logits, reduction_indices=0) \
            - intersection+epsilon

        mean_iou = tf.reduce_mean(intersection/union, name='mean_iou')

        eval_list = []

        eval_list.append(('mean_iou', mean_iou))

        return eval_list


def eval_image(hypes, gt_image, cnn_image):
    """."""
    thresh = np.array(range(0, 256))/255.0
    road_gt = gt_image[:, :, 2] > 0
    valid_gt = gt_image[:, :, 0] > 0

    FN, FP, posNum, negNum = seg.evalExp(road_gt, cnn_image,
                                         thresh, validMap=None,
                                         validArea=valid_gt)

    return FN, FP, posNum, negNum


def evaluate(hypes, sess, image_pl, softmax):
    data_dir = hypes['dirs']['data_dir']
    data_file = hypes['data']['val_file']
    data_file = os.path.join(data_dir, data_file)
    image_dir = os.path.dirname(data_file)

    thresh = np.array(range(0, 256))/255.0
    total_fp = np.zeros(thresh.shape)
    total_fn = np.zeros(thresh.shape)
    total_posnum = 0
    total_negnum = 0

    image_list = []

    with open(data_file) as file:
        for i, datum in enumerate(file):
                datum = datum.rstrip()
                image_file, gt_file = datum.split(" ")
                image_file = os.path.join(image_dir, image_file)
                gt_file = os.path.join(image_dir, gt_file)

                image = scp.misc.imread(image_file)
                gt_image = scp.misc.imread(gt_file)
                shape = image.shape

                feed_dict = {image_pl: image}

                output = sess.run([softmax], feed_dict=feed_dict)
                output_im = output[0][:, 1].reshape(shape[0], shape[1])

                if i % 5 == 0:
                    ov_image = seg.make_overlay(image, output_im)
                    name = os.path.basename(image_file)
                    image_list.append((name, ov_image))

                FN, FP, posNum, negNum = eval_image(hypes, gt_image, output_im)

                total_fp += FP
                total_fn += FN
                total_posnum += posNum
                total_negnum += negNum

    eval_dict = seg.pxEval_maximizeFMeasure(total_posnum, total_negnum,
                                            total_fn, total_fp,
                                            thresh=thresh)

    eval_list = []

    eval_list.append(('MaxF1', 100*eval_dict['MaxF']))
    eval_list.append(('BestThresh', 100*eval_dict['BestThresh']))
    eval_list.append(('Average Precision', 100*eval_dict['AvgPrec']))

    return eval_list, image_list
