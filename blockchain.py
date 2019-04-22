import hashlib
import json
import requests
import sys

from textwrap import dedent
from time import time
from uuid import uuid4
from urllib.parse import urlparse
from flask import Flask, jsonify, request

class Blockchain(object):

  def __init__(self):
    self.nodes = set()
    self.chain = []
    self.current_transactions = []
    self.new_block(proof=100, previous_hash='1')

  def register_node(self, address):
    parsed_url = urlparse(address)
    self.nodes.add(parsed_url.netloc)

  def valid_chain(self, chain):
    last_block, current_idx = chain[0], 1
    while current_idx < len(chain):
      block = chain[current_idx]
      if self.hash(last_block) is not block['previous_hash']: return False
      if not self.valid_proof(last_block['proof'], block['proof']): return False
      last_block = chain[current_idx]
      current_idx += 1
    return True

  def resolve_conflicts(self):
    new_chain, max_length = None, len(self.chain)
    for node in self.nodes:
      response = requests.get(f'http://{node}/chain')
      print(response.json())
      if response.status_code is 200:
        chain = response.json()['chain']
        length = len(chain)
        if length > max_length:
          max_length = length
          new_chain = chain
    if new_chain:
      self.chain = new_chain
      return True
    return False

  def new_block(self, proof, previous_hash):
    block = {
      'index': len(self.chain) + 1,
      'timestamp': time(),
      'transactions': self.current_transactions,
      'proof': proof,
      'previous_hash': previous_hash
    }

    self.current_transactions = []
    self.chain.append(block)
    return block

  def new_transaction(self, sender, recipient, amount):
    self.current_transactions.append({
        'sender': sender,
        'recipient': recipient,
        'amount': amount
      })
    return self.last_block['index'] + 1

  def proof_of_work(self, last_proof):
    proof = 0
    while not self.valid_proof(proof, last_proof):
      proof += 1
    return proof

  @staticmethod
  def valid_proof(proof, last_proof):
    guess = f'{last_proof}{proof}'.encode()
    guess_hash = hashlib.sha256(guess).hexdigest()
    return guess_hash[:4] == '0000'

  @staticmethod
  def hash(block):
    block_string = json.dumps(block, sort_keys=True).encode()
    return hashlib.sha256(block_string).hexdigest()

  @property
  def last_block(self):
    return self.chain[-1]
    

app = Flask(__name__)

node_identifier = str(uuid4()).replace('-', '')

blockchain = Blockchain()

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
  values = request.get_json()
  nodes = values.get('nodes')
  if nodes:
    for node in nodes: blockchain.register_node(node)
    response = {
      'message': 'New nodes have been added',
      'nodes': list(blockchain.nodes)
    }
    return jsonify(response), 201
  else:
    response = {
      'message': 'Please provide a valid list of nodes'
    }
    return jsonify(response), 400


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
  replaced = blockchain.resolve_conflicts()
  if replaced:
    response = {
      'message': 'Our chain was replaced',
      'new_chain': blockchain.chain
    }
  else:
    response = {
      'message': 'Our chain is authoritative',
      'chain': blockchain.chain
    }
  return jsonify(response), 200

@app.route('/mine', methods=['GET'])
def mine():
  last_block = blockchain.last_block
  last_proof = last_block['proof']
  proof = blockchain.proof_of_work(last_proof)

  blockchain.new_transaction(
      sender='0',
      recipient=node_identifier,
      amount=1
    )
  
  previous_hash = blockchain.hash(last_proof)
  block = blockchain.new_block(proof,previous_hash)
  response = {
      'message': 'New block forged',
      'index': block['index'],
      'transactions': block['transactions'],
      'proof': block['proof'],
      'previous_hash': block['previous_hash']
    }
  return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
  data = request.get_json()
  required = ['sender', 'recipient','amount']
  if not all(k in data for k in required):
    return 'Missing data', 400
  index = blockchain.new_transaction(data['sender'], data['recipient'], data['amount'])
  response = { 'message': f'Added a new transaction to Block # {index}' }
  return jsonify(response), 201

@app.route('/chain', methods=['GET'])
def full_chain():
  response = {
    'chain': blockchain.chain,
    'length': len(blockchain.chain)
  }
  return jsonify(response), 200


if __name__ == '__main__':
  port = int(sys.argv[1])
  print('Running node on port:', port)
  app.run(host='0.0.0.0', port=port)