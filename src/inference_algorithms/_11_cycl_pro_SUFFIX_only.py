"""
this file is build based on the code found in evaluate_suffix_and_remaining_time.py

here the beam search (with breath-first-search) is implemented, to find compliant prediction

Author: Anton Yeshchenko
"""
from __future__ import division
from Queue import PriorityQueue
from datetime import timedelta
from itertools import izip
# noinspection PyProtectedMember
from jellyfish._jellyfish import damerau_levenshtein_distance
from keras.models import load_model
from sklearn import metrics
from inspect import getsourcefile
from shared_variables import activate_settings
from formula_verificator import verify_formula_as_compliant
from support_scripts.prepare_data import amplify, get_symbol_ampl
from support_scripts.prepare_data import encode
from support_scripts.prepare_data_resource import prepare_testing_data, select_declare_verified_traces

import csv
import numpy as np
import time
import distance
import os.path
import sys

current_path = os.path.abspath(getsourcefile(lambda: 0))
current_dir = os.path.dirname(current_path)
parent_dir = current_dir[:current_dir.rfind(os.path.sep)]

sys.path.insert(0, parent_dir)


def run_experiments(log_identificator, formula_type, rnn_type):

    eventlog, \
        path_to_model_file_cf, \
        path_to_model_file_cfr, \
        path_to_declare_model_file, \
        beam_size, \
        prefix_size_pred_from, \
        prefix_size_pred_to, \
        formula = activate_settings(log_identificator, formula_type)

    if rnn_type == "CF":
        path_to_model_file = path_to_model_file_cf
    elif rnn_type == "CFR":
        path_to_model_file = path_to_model_file_cfr

    start_time = time.time()

    # prepare the data
    lines, \
        lines_id, \
        lines_group, \
        lines_t, \
        lines_t2, \
        lines_t3, \
        lines_t4, \
        maxlen, \
        chars, \
        chars_group, \
        char_indices, \
        char_indices_group, \
        divisor, \
        divisor2, \
        divisor3, \
        predict_size, \
        target_indices_char, \
        target_indices_char_group,\
        target_char_indices, \
        target_char_indices_group = prepare_testing_data(eventlog)

    # this is the beam stack size, means how many "best" alternatives will be stored
    one_ahead_gt = []
    one_ahead_pred = []

    # find cycles and modify the probability functionality goes here
    stop_symbol_probability_amplifier_current = 1

    # load model, set this to the model generated by train.py
    model = load_model(path_to_model_file)

    class NodePrediction:
        def __init__(self, data, crop_line, tot_predicted_time, probability_of=0):
            self.data = data
            self.cropped_line = crop_line
            self.total_predicted_time = tot_predicted_time
            self.probability_of = probability_of

    # make predictions
    with open('output_files/final_experiments/results/LTL/%s_%s.csv' % (eventlog[:-4], rnn_type), 'wb') as csvfile:
        spamwriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        spamwriter.writerow(["Prefix length",
                             "Groud truth",
                             "Predicted",
                             "Levenshtein",
                             "Damerau",
                             "Jaccard",
                             "Ground truth times",
                             "Predicted times",
                             "RMSE",
                             "MAE",
                             "Median AE"])
        for prefix_size in range(prefix_size_pred_from, prefix_size_pred_to):
            print(prefix_size)

            lines_s, \
                lines_id_s, \
                lines_group_s, \
                lines_t_s, \
                lines_t2_s, \
                lines_t3_s, \
                lines_t4_s = select_declare_verified_traces(path_to_declare_model_file,
                                                            lines,
                                                            lines_id,
                                                            lines_group,
                                                            lines_t,
                                                            lines_t2,
                                                            lines_t3,
                                                            lines_t4,
                                                            prefix_size)
            print("prefix size: " + str(prefix_size))
            print("formulas verified: " + str(len(lines_s)) + " out of : " + str(len(lines)))
            counterr = 0
            for line, times, times2, times3 in izip(lines_s, lines_t_s, lines_t2_s, lines_t3_s):
                times.append(0)
                cropped_line = ''.join(line[:prefix_size])
                cropped_times = times[:prefix_size]
                cropped_times3 = times3[:prefix_size]
                if len(times2) < prefix_size:
                    continue  # make no prediction for this case, since this case has ended already

                # initialize root of the tree for beam search
                total_predicted_time_initialization = 0
                search_node_root = NodePrediction(encode(cropped_line,
                                                         cropped_times,
                                                         cropped_times3,
                                                         maxlen,
                                                         chars,
                                                         char_indices,
                                                         divisor,
                                                         divisor2),
                                                  cropped_line,
                                                  total_predicted_time_initialization)

                ground_truth = ''.join(line[prefix_size:prefix_size+predict_size])
                ground_truth_t = times2[prefix_size-1]
                case_end_time = times2[len(times2)-1]
                ground_truth_t = case_end_time-ground_truth_t

                queue_next_steps = PriorityQueue()
                queue_next_steps.put((-search_node_root.probability_of, search_node_root))

                queue_next_steps_future = PriorityQueue()
                start_of_the_cycle_symbol = " "
                found_sattisfying_constraint = False

                current_beam_size = beam_size
                current_prediction_premis = None

                for i in range(predict_size):
                    for k in range(current_beam_size):
                        if queue_next_steps.empty():
                            break

                        _, current_prediction_premis = queue_next_steps.get()

                        if not found_sattisfying_constraint:
                            if verify_formula_as_compliant(current_prediction_premis.cropped_line,
                                                           formula,
                                                           prefix_size):
                                # the formula verified and we can just finish the predictions
                                # beam size is 1 because predict only sequence of events
                                current_beam_size = 1
                                current_prediction_premis.probability_of = 0.0
                                # overwrite new queue
                                queue_next_steps_future = PriorityQueue()
                                found_sattisfying_constraint = True

                        enc = current_prediction_premis.data
                        temp_cropped_line = current_prediction_premis.cropped_line
                        y = model.predict(enc, verbose=0)  # make predictions
                        # split predictions into seperate activity and time predictions
                        y_char = y[0][0]
                        y_t = y[1][0][0]

                        if y_t < 0:
                            y_t = 0
                        cropped_times.append(y_t)

                        if not i == 0:
                            stop_symbol_probability_amplifier_current, start_of_the_cycle_symbol =\
                                amplify(temp_cropped_line)

                        # in not reached, function :choose_next_top_descendant: will backtrack
                        y_t = y_t * divisor3
                        cropped_times3.append(cropped_times3[-1] + timedelta(seconds=y_t))

                        for j in range(current_beam_size):
                            temp_prediction = get_symbol_ampl(y_char, target_indices_char,
                                                              target_char_indices, start_of_the_cycle_symbol,
                                                              stop_symbol_probability_amplifier_current, j)
                            # end of case was just predicted, therefore, stop predicting further into the future
                            if temp_prediction == '!':
                                if verify_formula_as_compliant(temp_cropped_line, formula, prefix_size):
                                    one_ahead_pred.append(current_prediction_premis.total_predicted_time)
                                    one_ahead_gt.append(ground_truth_t)
                                    stop_symbol_probability_amplifier_current = 1
                                    print('! predicted, end case')
                                    queue_next_steps = PriorityQueue()
                                    break
                                else:
                                    continue

                            temp_cropped_line = current_prediction_premis.cropped_line + temp_prediction
                            temp_total_predicted_time = current_prediction_premis.total_predicted_time + y_t
                            temp_state_data = encode(temp_cropped_line, cropped_times, cropped_times3,
                                                     maxlen, chars, char_indices, divisor, divisor2)
                            probability_this = np.sort(y_char)[len(y_char) - 1 - j]

                            temp = NodePrediction(temp_state_data,
                                                  temp_cropped_line,
                                                  temp_total_predicted_time,
                                                  current_prediction_premis.probability_of + np.log(probability_this))
                            queue_next_steps_future.put((-temp.probability_of, temp))
                            print 'INFORMATION: ' + str(counterr) + ' ' + str(i) + ' ' + str(k) + ' ' + str(j) + ' ' + \
                                temp_cropped_line[prefix_size:] + "     " + str(temp.probability_of)

                    queue_next_steps = queue_next_steps_future
                    queue_next_steps_future = PriorityQueue()

                counterr += 1

                if current_prediction_premis is None:
                    print "Cannot find any trace that is compliant with formula given current beam size"
                    break

                output = []

                if current_prediction_premis is None:
                    predicted = u""
                    total_predicted_time = 0
                else:
                    predicted = (current_prediction_premis.cropped_line[prefix_size:])
                    total_predicted_time = current_prediction_premis.total_predicted_time

                if len(ground_truth) > 0:
                    output.append(prefix_size)
                    output.append(unicode(ground_truth).encode("utf-8"))
                    output.append(unicode(predicted).encode("utf-8"))
                    output.append(1 - distance.nlevenshtein(predicted, ground_truth))
                    dls = 1 - (damerau_levenshtein_distance(unicode(predicted),
                                                            unicode(ground_truth)) / max(len(predicted),
                                                                                         len(ground_truth)))
                    if dls < 0:
                        dls = 0
                    # we encountered problems with Damerau-Levenshtein Similarity on some linux machines where the
                    # default character encoding of the operating system caused it to be negative, this should never
                    # be the case
                    output.append(dls)
                    output.append(1 - distance.jaccard(predicted, ground_truth))
                    output.append(ground_truth_t)
                    output.append(total_predicted_time)
                    output.append('')
                    output.append(metrics.mean_absolute_error([ground_truth_t], [total_predicted_time]))
                    output.append(metrics.median_absolute_error([ground_truth_t], [total_predicted_time]))
                    spamwriter.writerow(output)

    print("TIME TO FINISH --- %s seconds ---" % (time.time() - start_time))
