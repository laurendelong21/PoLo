import os.path as osp
import statistics
import os
import pandas as pd
import numpy as np


def calculate_query_metrics(query_metrics, answer_pos):
    if answer_pos is not None:
        query_metrics[5] += 1.0 / (answer_pos + 1)  # MRR
        if answer_pos < 20:
            query_metrics[4] += 1  # Hits@20
            if answer_pos < 10:
                query_metrics[3] += 1  # Hits@10
                if answer_pos < 5:
                    query_metrics[2] += 1  # Hits@5
                    if answer_pos < 3:
                        query_metrics[1] += 1  # Hits@3
                        if answer_pos < 1:
                            query_metrics[0] += 1  # Hits@1
    return query_metrics


def get_metrics_by_length(answer_positions, path_lengths):
    """Gets the query metrics per path length"""
    metrics_by_len = dict()

    for length, pairs in path_lengths.items():
        metrics_by_len[length] = np.zeros(6)
        for pair in pairs:
            metrics_by_len[length] = calculate_query_metrics(metrics_by_len[length], answer_positions[pair])

    return metrics_by_len


def get_metrics_dict(experiment_dir):
    """Pass the path of a directory for a single experiment (which might contain multiple runs/replicates)

    :param experiment_dir: directory for a single experiment (which might contain multiple runs/replicates)
    :returns: a dictionary of the metric names to their average and standard deviation
    """
    exp_name = osp.basename(experiment_dir)

    # all experimental runs
    runs = os.listdir(experiment_dir)

    hits_values = {"Hits@1": [], "Hits@3": [], "Hits@10": [], "MRR": []}
    pruned_values = {
        "Hits@1_rule": [],
        "Hits@3_rule": [],
        "Hits@10_rule": [],
        "MRR_rule": [],
    }

    for run in runs:
        run_dir = osp.join(experiment_dir, run)
        if not osp.isdir(run_dir) or "TEST" not in run_dir:
            continue
        # for each run in an experiment dir, get the paths dir
        fpath = osp.join(experiment_dir, f"{run}/scores.txt")

        # Open the file for reading
        with open(fpath, "r") as file:
            # Read the file line by line
            for line in file:
                split_line = line.split(":")
                # Find each metric
                if split_line[0] in set(hits_values.keys()):
                    hits_values[split_line[0]].append(float(split_line[1].strip()))
                elif split_line[0] in set(pruned_values.keys()):
                    pruned_values[split_line[0]].append(float(split_line[1].strip()))

    hits_values = {
        key: (round(sum(val) / len(val), 3), round(statistics.stdev(val), 3))
        for key, val in hits_values.items()
    }
    pruned_values = {
        key.split("_rule")[0]: (
            round(sum(val) / len(val), 3),
            round(statistics.stdev(val), 3),
        )
        for key, val in pruned_values.items()
    }

    scores = {f"{exp_name} metrics": hits_values, f"{exp_name} metrics (pruned)": pruned_values}
    scores_df = pd.DataFrame(scores)

    # Write the rounded DataFrame to a TSV file
    output_file = osp.join(experiment_dir, "experiment_metrics.tsv")
    scores_df.to_csv(output_file, sep="\t", index=True)

    print(scores_df)

    return scores


def process_mars_metrics(results_dir):
    """Gets and formats the metrics from MARS into a table. Simply pass a directory with multiple experiments in it,
    and this will compute the average and stdev
    """
    final_metrics = dict()

    # all experimental runs
    experiments = os.listdir(results_dir)

    for exp in experiments:
        exp_path = osp.join(results_dir, exp)
        if not osp.isdir(exp_path) or 'TEST' not in exp_path:
            continue
        # for each experiment dir, get the metrics dict
        metrics_dict = get_metrics_dict(exp_path)
        for key, val in metrics_dict.items():
            final_metrics[key] = val

    metrics_df = pd.DataFrame(final_metrics).transpose().sort_index()

    # Write the rounded DataFrame to a TSV file
    output_file = osp.join(results_dir, "metrics.tsv")
    metrics_df.to_csv(output_file, sep="\t", index=True)