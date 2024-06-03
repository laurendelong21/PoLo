input_dir="datasets/MOA-net-protclass/"
base_output_dir="output/MOA-net-protclass-polo/"
update_confs=0
path_length=3
total_iterations=1000
eval_every=10
patience=2
Lambda=1
only_body=0
embedding_size=256
hidden_size=64
LSTM_layers=2
beta="0.025 0.05"
gamma_baseline="0.05 0.5"
learning_rate=0.001
max_num_actions=150
train_entity_embeddings=1
use_entity_embeddings=1
batch_size=128
num_rollouts=100
test_rollouts=100
load_model=0
model_load_path="./models/MOA-net-protclass-polo/model.ckpt"
