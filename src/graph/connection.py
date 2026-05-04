


"""
This is a script is for setting up Neo4j driver to communicate with the local instance.
"""



import os
from neo4j import GraphDatabase, Driver


def make_driver() -> Driver:
    ...