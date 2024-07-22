import csv
import numpy as np
from collections import Counter
import random
import networkx as nx


"""The script responsible for generating the graph structure and next steps, 
but for each step, ensures to mask the connections representing the true answers so there is no cheating
"""


class RelationEntityGrapher(object):
    def __init__(self, triple_store, entity_vocab, relation_vocab, max_branching, class_threshhold=None):
        """Initializes the creation of the graph.
            :param triple_store: the file location of the KG triples
            :param entity_vocab: the file location of the ID mappings for entities
            :param relation_vocab: the file location of the ID mappings for relations
            :param max_branching: the max number of outgoing edges from any given source node
            :param class_threshhold: (optional) the max number of edges of any class to keep in the graph
        """
        self.ePAD = entity_vocab['PAD']  # the ID of the PAD token for entities
        self.rPAD = relation_vocab['PAD']  # the ID of the PAD token for relations
        self.triple_store = triple_store
        self.entity_vocab = entity_vocab
        self.relation_vocab = relation_vocab
        self.G = nx.MultiDiGraph()
        self.class_threshhold = class_threshhold
        # self.store is a dictionary storing all the connections from a node
        self.store = None
        self.hubs = set()
        # self.array_store is a 3D array initialized with the PAD values
        # it contains a 2D matrix for entities and relations each
        self.array_store = np.ones((len(entity_vocab), max_branching, 2), dtype=np.dtype('int32'))
        self.array_store[:, :, 0] *= self.ePAD
        self.array_store[:, :, 1] *= self.rPAD
        self.masked_array_store = None
        self.rev_entity_vocab = dict([(v, k) for k, v in entity_vocab.items()])
        self.rev_relation_vocab = dict([(v, k) for k, v in relation_vocab.items()])
        self.paired_relation_vocab = dict()
        for k, v in relation_vocab.items():
            if '_' in k:
                k_pair = k.strip('_')
            else:
                k_pair = f'_{k}'
            if k_pair in self.relation_vocab.keys():
                self.paired_relation_vocab[v] = self.relation_vocab[k_pair]
        self.create_graph()
        print("KG constructed.")

    def create_graph(self):
        """Stores all of the KG triples in a networkx graph
        """
        with open(self.triple_store) as triple_file_raw:
            triple_file = csv.reader(triple_file_raw, delimiter='\t')
            for line in triple_file:
                # parse and map each to its unique ID
                e1 = self.entity_vocab[line[0]]
                r = self.relation_vocab[line[1]]
                e2 = self.entity_vocab[line[2]]

                if e1 not in self.G.nodes:
                    self.G.add_node(e1)
                if e2 not in self.G.nodes:
                    self.G.add_node(e2)
                self.G.add_edge(e1, e2, key=r)

        if self.class_threshhold:
            self.reduce_graph()

        # prune by the branching factor
        self.prune_graph()


    def get_edge_counter(self):
        """Gets a counter dictionary of the edge types in the graph"""
        edge_types = list()
        for edge in self.G.edges(keys=True):
            edge_type = edge[2]
            edge_types.append(edge_type)
        edge_types = dict(Counter(edge_types))
        return edge_types
    

    def get_edges_of_type(self, edge_type):
        edges_of_type = {(s, t, k) for s, t, k in self.G.edges(keys=True) if k == edge_type}
        source_nodes = {s for s, _, _ in edges_of_type}
        target_nodes = {t for _, t, _ in edges_of_type}
        return edges_of_type, source_nodes, target_nodes


    def reduce_graph(self):
        """
        If class_threshhold is passed, this will reduce the graph by removing edges of any classes above the threshhold.
        """
        edge_types = self.get_edge_counter()
        count = 0

        for edge_type in edge_types.keys():
            if edge_types[edge_type] <= self.class_threshhold:
                continue

            # get the reverse edge type:
            reverse_edge_type = self.paired_relation_vocab[edge_type] if edge_type in self.paired_relation_vocab else None

            _, source_nodes, target_nodes = self.get_edges_of_type(edge_type)

            while edge_types[edge_type] > self.class_threshhold:
                
                node_with_highest_degree = max(source_nodes, key=lambda n: self.G.out_degree(n))
                # Find the neighbor of node_with_highest_degree with the largest degree
                neighbors = [node for node in self.G.neighbors(node_with_highest_degree) if node in target_nodes]
                neighbor_of_highest_degree = max(neighbors, key=lambda n: self.G.out_degree(n))
                # remove the edge between prot_with_highest_degree and neighbor_of_highest_degree
                self.G.remove_edge(node_with_highest_degree, neighbor_of_highest_degree)
                edge_types[edge_type] -= 1
                if reverse_edge_type:
                    self.G.remove_edge(neighbor_of_highest_degree, node_with_highest_degree)
                    edge_types[reverse_edge_type] -= 1
                count += 1
                if count % 1000 == 0:
                    print(count, self.G.number_of_edges())


    def prune_graph(self):
        """Prunes the graph to the specified branching factor"""
        source_nodes = [node for node in self.G.nodes() if self.G.out_degree(node) > 0]
        for source_node in source_nodes :  # for every source node / dict key
            # first, give the agent the option to remain at every source node:
            self.array_store[source_node, 0, 1] = self.relation_vocab['NO_OP']  # no operation / no movement
            self.array_store[source_node, 0, 0] = source_node  # self-connection / stay where you are
            num_actions = 1

            # shuffle the keys so the order is not determined by the input file
            target_nodes = list(nx.neighbors(self.G, source_node))
            random.shuffle(target_nodes)

            for target_node in target_nodes:  # for each connecting node,
                # if we reached the max number of actions, stop
                if num_actions == self.array_store.shape[1]:
                    break
                # store the number of the current outgoing edge as an index
                self.array_store[source_node, num_actions, 0] = target_node
                self.array_store[source_node, num_actions, 1] = self.G[source_node][target_node]['type']
                num_actions += 1


    def return_next_actions(self, current_entities, start_entities, query_relations, end_entities, all_correct_answers,
                            is_last_step, rollouts):
        """Using the matrices in self.array_store, return the actions that could be taken
            by the agent from a given node. Mask the source nodes from the true labels in the dataset.
        :param current_entities: a list of the entities which the agent is currently considering
        :param start_entities: an array containing all the source nodes within the data batch triples
        :param query_relations: an array containing all relations within the data batch triples
        :param end_entities: an array containing all the target nodes within the data batch triples
        :param all_correct_answers: a mapping from sink nodes (keys) to tuples of source nodes and relations from which they are reachable
        :param is_last_step: boolean indicating whether it's the max path length

        :returns: a copy of self.array_store in which (1) only the next possible actions are shown, and (2) the
            true labels from the dataset are masked so that the model can not cheat
        """
        # get only the connections from the entities currently being considered
        ret = self.array_store[current_entities, :, :].copy()
        for i in range(current_entities.shape[0]):
            # if we still have any beginning nodes:
            if current_entities[i] == start_entities[i]:
                # get the entities and relations which are accessible from that entity in the KG
                entities = ret[i, :, 0]  # vector of target nodes connected to i
                relations = ret[i, :, 1]  # vector of relations connected to i
                # identify the connections in the batch and mask them 
                # mask is a vector of boolean indications, where if True, the mask 
                mask = np.logical_and(relations == query_relations[i], entities == end_entities[i])
                ret[i, :, 0][mask] = self.ePAD
                ret[i, :, 1][mask] = self.rPAD
            if is_last_step:
                entities = ret[i, :, 0]  # vector of target nodes connected to source node at i
                correct_e2 = end_entities[i]  # the sink node in triple index i
                # for each of the sink nodes connected to source nodes i,
                for j in range(entities.shape[0]):
                    # here we hide correct answers which are not in the current set - no cheating
                    if entities[j] in all_correct_answers[i // rollouts] and entities[j] != correct_e2:
                        ret[i, :, 0][j] = self.ePAD
                        ret[i, :, 1][j] = self.rPAD
        return ret
