import pickle
from keras.preprocessing.sequence import pad_sequences
import tensorflow as tf
import models
import numpy as np
import os
import vis_util
import argparse

parser = argparse.ArgumentParser()

parser.add_argument("modelname", help="specify the name of the model", type=str)

parser.add_argument("--test", action="store_true", default=False, help="Only test and produce visualisation")


args = parser.parse_args()

# Defining constants
max_len = 30
train_size = 400
test_size = 100
batch_size = 10
lstm_size = 20
num_epochs = 1
embedding_dim = 20

#Loading data:
print("Loading vocabulary")
f = open("data/vocab.pkl", "rb")
word_dict = pickle.load(f)
f.close()

print("Loading dataset")
f = open("out/samples.pkl", "rb")
samples = pickle.load(f)
f.close()


f = open('data/effect_list.pkl', 'rb') 
effect_list = pickle.load(f)
f.close()

f = open('data/embedding_matrix.pkl', 'rb') 
embedding_matrix = pickle.load(f)
f.close()

all_x = pad_sequences(np.asarray([s['sentence_ind'] for s in samples]), maxlen=30, padding='post')
all_y = np.asarray([s['label'] for s in samples])

train_x = all_x[:train_size]
train_y = all_y[:train_size]

test_x = all_x[train_size: train_size+test_size]
test_y = all_y[train_size: train_size+test_size]

sess = tf.Session()
print("Buidling the model")
model = models.SentimentModelWithAttention(batch_size=batch_size,
                       lstm_size = lstm_size,
                       max_len = max_len,
                       keep_probs=0.8,
                       embeddings_dim=embedding_matrix.shape[1], vocab_size=embedding_matrix.shape[0],
                       is_train=True,
                       use_reg = True)


sess.run(tf.global_variables_initializer())
saver = tf.train.Saver()
ckpt_file = "model/" + args.modelname
if args.test:  
    # TODO
    saver.restore(sess, ckpt_file)
    print('Test accuracy = ', model.evaluate_accuracy(sess, test_x, test_y))
else:
    sess.run(tf.assign(model.embedding_w, embedding_matrix))

    if os.path.exists(ckpt_file+".meta"):
        print('Restoring Model')
        saver.restore(sess, ckpt_file)

    print('Training..')
    for i in range(num_epochs):
        epoch_loss, epoch_accuracy = model.train_for_epoch(sess, train_x, train_y)
        print(i,'loss: ', epoch_loss, 'acc: ', epoch_accuracy)
        #print('Train accuracy = ', model.evaluate_accuracy(sess, train_x, train_y))
        print('Test accuracy = ', model.evaluate_accuracy(sess, test_x, test_y))
    if not os.path.exists('model'):
        os.mkdir('model')

    print("Saving the model")
    saver.save(sess, ckpt_file)
    print("Finished")


print("Producing visualization")
htmls = vis_util.knit(test_x, test_y, word_dict, effect_list, model, sess, 100)
f = open("model/vis.html", "wb")
for i in htmls:
    f.write(i)
f.close()


