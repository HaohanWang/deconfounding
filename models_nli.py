import tensorflow as tf
import numpy as np
from model_utils import dense_layer, attention_layer, get_reg, lstm_layer
from models import Model


class AdditiveModel(object):
    def __init__(self, pred_model, keyword_model):
        self.pred_model = pred_model
        self.keyword_model = keyword_model
        assert self.pred_model.batch_size == self.keyword_model.batch_size
        self.batch_size = self.pred_model.batch_size
        self.use_alphas = False
        if self.pred_model.use_alphas:
            self.use_alphas = True
            self.alphas_hypo = self.pred_model.alphas_hypo
            self.alphas_prem = self.pred_model.alphas_prem
        self.build_model()

    def build_model(self):
        self.logits = self.pred_model.logits + tf.stop_gradient(self.keyword_model.logits)
        self.y = tf.nn.softmax(self.logits)
        self.cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(
            labels=tf.one_hot(self.pred_model.y_holder, depth=3), logits=self.logits))

        self.accuracy = tf.reduce_mean(tf.cast(tf.equal(self.pred_model.y_holder, tf.argmax(self.pred_model.y, 1)), tf.float32))
        self.optimizer = tf.train.GradientDescentOptimizer(learning_rate=self.pred_model.learning_rate)
        self.train_op = self.optimizer.minimize(self.cost)


    def train_for_epoch(self, sess, train_x, train_y):
        # cur_state = sess.run(init_state)
        batches_per_epoch = train_x.shape[0] // self.batch_size
        epoch_loss = 0.0
        epoch_accuracy = 0.0
        for idx in range(batches_per_epoch):
            batch_idx = np.random.choice(train_x.shape[0], size=self.batch_size, replace=False)
            batch_xs = train_x[batch_idx, :]
            batch_ys = train_y[batch_idx]
            batch_loss, _, batch_accuracy = sess.run([self.cost, self.train_op, self.accuracy],
                                                     feed_dict={self.pred_model.x_holder: batch_xs,
                                                                self.pred_model.y_holder: batch_ys,
                                                                self.keyword_model.x_holder: batch_xs,
                                                                self.keyword_model.y_holder: batch_ys})
            epoch_loss += batch_loss
            epoch_accuracy += batch_accuracy
        return epoch_loss / batches_per_epoch, epoch_accuracy / batches_per_epoch

    def predict_no_alphas(self, sess, test_x):
        pred_y = sess.run(self.pred_model.y, feed_dict={self.pred_model.x_holder: test_x})
        return pred_y

    def predict(self, sess, test_x):
        pred_y, alphas_hypo, alphas_prem = sess.run([self.pred_model.y, self.pred_model.alphas_hypo, self.pred_model.alphas_prem], feed_dict={self.pred_model.x_holder: test_x})
        return pred_y, alphas_hypo, alphas_prem

    def evaluate_accuracy(self, sess, test_x, test_y):
        test_accuracy = 0.0
        test_batches = test_x.shape[0] // self.batch_size
        for i in range(test_batches):
            test_idx = range(i * self.batch_size, (i + 1) * self.batch_size)
            test_xs = test_x[test_idx, :]
            test_ys = test_y[test_idx]
            pred_ys = self.predict_no_alphas(sess, test_xs)
            test_accuracy += np.sum(np.argmax(pred_ys, axis=1) == test_ys)
        test_accuracy /= (test_batches * self.batch_size)
        return test_accuracy

    def evaluate_capturing(self, sess, test_x, test_y, effect_dict):
        raise NotImplementedError


class NLIModel(Model):

    def build_model(self):
        raise NotImplementedError

    def train_for_epoch(self, sess, train_x, train_y):
        # cur_state = sess.run(init_state)
        batches_per_epoch = train_x.shape[0] // self.batch_size
        epoch_loss = 0.0
        epoch_accuracy = 0.0
        for idx in range(batches_per_epoch):
            batch_idx = np.random.choice(train_x.shape[0], size=self.batch_size, replace=False)
            batch_xs = train_x[batch_idx, :, :]
            batch_ys = train_y[batch_idx]
            batch_loss, _, batch_accuracy = sess.run([self.cost, self.train_op, self.accuracy],
                                                     feed_dict={self.x_holder: batch_xs,
                                                                self.y_holder: batch_ys})
            epoch_loss += batch_loss
            epoch_accuracy += batch_accuracy
        return epoch_loss / batches_per_epoch, epoch_accuracy / batches_per_epoch

    def predict(self, sess, test_x):
        pred_y, alphas_hypo, alphas_prem = sess.run([self.y, self.alphas_hypo, self.alphas_prem], feed_dict={self.x_holder: test_x})
        return pred_y, alphas_hypo, alphas_prem

    def evaluate_accuracy(self, sess, test_x, test_y):
        test_accuracy = 0.0
        test_batches = test_x.shape[0] // self.batch_size
        for i in range(test_batches):
            test_idx = range(i * self.batch_size, (i + 1) * self.batch_size)
            test_xs = test_x[test_idx, :, :]
            test_ys = test_y[test_idx]
            pred_ys = self.predict_no_alphas(sess, test_xs)
            test_accuracy += np.sum(np.argmax(pred_ys, axis=1) == test_ys)
        test_accuracy /= (test_batches * self.batch_size)
        return test_accuracy

    def build_inputs(self):
        # input shape = (batch_size, sentence_length, emb_dim)
        self.x_holder = tf.placeholder(tf.int32, shape=[None, 2, self.max_len])
        self.y_holder = tf.placeholder(tf.int64, shape=[None])
        self.seq_len_hypo = tf.cast(tf.reduce_sum(tf.sign(self.x_holder[:, 0, :]), axis=1), tf.int32)
        self.seq_len_prem = tf.cast(tf.reduce_sum(tf.sign(self.x_holder[:, 1, :]), axis=1), tf.int32)

    def build_embedding(self):
        if self.use_embedding:
            self.embedding_w = tf.get_variable('embed_w', shape=[self.vocab_size, self.emb_dim],
                                               initializer=tf.random_uniform_initializer())
        else:
            self.embedding_w = tf.one_hot(list(range(self.vocab_size)), depth=self.vocab_size)

        self.e_hypo = tf.nn.embedding_lookup(self.embedding_w, self.x_holder[:, 0, :])
        self.e_prem = tf.nn.embedding_lookup(self.embedding_w, self.x_holder[:, 1, :])


class RegAttention(NLIModel):
    def __init__(self, batch_size=10, max_len=30, lstm_size=20, vocab_size=10000, embeddings_dim=20, keep_probs=0.9,
                 attention_size=16, use_embedding=True, reg="none", lam=None, sparse=False, learning_rate=0.1):
        Model.__init__(self, batch_size, max_len, vocab_size, embeddings_dim, use_embedding,
                       learning_rate=learning_rate)
        self.lstm_size = lstm_size
        self.attention_size = attention_size
        self.reg = reg
        self.lam = lam
        self.epsilon = 1e-10
        self.sparse = sparse
        self.keep_probs = keep_probs
        self.use_alphas = True
        self.build_model()

    def build_model(self):
        # input shape = (batch_size, sentence_length, emb_dim)

        rnn_outputs_hypo, final_state_hypo = lstm_layer(self.e_hypo, self.lstm_size, self.batch_size, self.seq_len_hypo, "hypo")
        rnn_outputs_prem, final_state_prem = lstm_layer(self.e_prem, self.lstm_size, self.batch_size, self.seq_len_prem, "prem")

        last_output_hypo, alphas_hypo = attention_layer(self.attention_size, rnn_outputs_hypo, "encoder_hypo", sparse=self.sparse)
        last_output_prem, alphas_prem = attention_layer(self.attention_size, rnn_outputs_prem, "encoder_prem", sparse=self.sparse)

        self.alphas_hypo = alphas_hypo
        self.alphas_prem = alphas_prem
        self.logits = dense_layer(tf.concat([last_output_hypo, last_output_prem], axis=1), 3, activation=None, name="pred_out")
        self.y = tf.nn.softmax(self.logits)

        # WARNING: This op expects unscaled logits, since it performs a softmax on logits internally for efficiency.
        # Do not call this op with the output of softmax, as it will produce incorrect results.
        self.cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(
            labels=tf.one_hot(self.y_holder, depth=3), logits=self.logits))

        reg1 = get_reg(alphas_hypo, lam=self.lam, type=self.reg)
        reg2 = get_reg(alphas_prem, lam=self.lam, type=self.reg)
        self.cost += reg1 + reg2

        self.accuracy = tf.reduce_mean(tf.cast(tf.equal(self.y_holder, tf.argmax(self.y, 1)), tf.float32))

        self.optimizer = tf.train.GradientDescentOptimizer(self.learning_rate)
        self.train_op = self.optimizer.minimize(self.cost)


class LSTMPredModelWithMLPKeyWordModelAdvTrain(NLIModel):
    def __init__(self, batch_size=10, max_len=30, lstm_size=20, vocab_size=10000, embeddings_dim=20, keep_probs=0.9,
                 attention_size=16, use_embedding=True, reg="none", lam=None, sparse=False, kwm_lstm_size=20,
                 learning_rate=0.1):
        Model.__init__(self, batch_size, max_len, vocab_size, embeddings_dim, use_embedding,
                       learning_rate=learning_rate)
        self.lstm_size = lstm_size
        self.attention_size = attention_size
        self.reg = reg
        self.lam = lam
        self.kwm_lstm_size = kwm_lstm_size
        self.sparse = sparse
        self.keep_probs = keep_probs
        self.use_alphas = True
        self.build_model()

    def build_model(self):
        rnn_outputs_hypo, final_state_hypo = lstm_layer(self.e_hypo, self.lstm_size, self.batch_size, self.seq_len_hypo, "hypo")
        rnn_outputs_prem, final_state_prem = lstm_layer(self.e_prem, self.lstm_size, self.batch_size, self.seq_len_prem, "prem")

        last_output_hypo, alphas_hypo = attention_layer(self.attention_size, rnn_outputs_hypo, "encoder_hypo", sparse=self.sparse)
        last_output_prem, alphas_prem = attention_layer(self.attention_size, rnn_outputs_prem, "encoder_prem", sparse=self.sparse)
        self.alphas_hypo = alphas_hypo
        self.alphas_prem = alphas_prem
        self.logits = dense_layer(tf.concat([last_output_hypo, last_output_prem], axis=1), 3, activation=None, name="pred_out")
        self.y = tf.nn.softmax(self.logits)


        adv_in_hypo = tf.reshape(self.e_hypo, [-1, self.e_hypo.shape[1] * self.e_hypo.shape[2]])
        adv_in_prem = tf.reshape(self.e_prem, [-1, self.e_prem.shape[1] * self.e_hypo.shape[2]])
        """
        ### Debug ###
        self.w_adv = tf.get_variable("w", shape=[adv_in.shape[-1], 2],
                                     initializer=tf.truncated_normal_initializer())
        self.b_adv = tf.get_variable("b", shape=[2], dtype=tf.float32)

        adv_logits = tf.matmul(adv_in, self.w_adv) + self.b_adv
        ############
        """
        adv_logits = dense_layer(tf.concat([adv_in_hypo, adv_in_prem], axis=1), 3, activation=None, name="adv_encoder")
        adv_cost = 1 / tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(
            labels=tf.one_hot(self.y_holder, depth=3), logits=adv_logits))

        self.cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(
            labels=tf.one_hot(self.y_holder, depth=3), logits=self.logits))
        self.cost = self.cost + 0.01 * adv_cost

        self.accuracy = tf.reduce_mean(tf.cast(tf.equal(self.y_holder, tf.argmax(self.y, 1)), tf.float32))

        self.optimizer = tf.train.GradientDescentOptimizer(self.learning_rate)
        self.train_op = self.optimizer.minimize(self.cost)


class LSTMPredModel(NLIModel):
    def __init__(self, batch_size=10, max_len=30, lstm_size=20, vocab_size=10000, embeddings_dim=20, keep_probs=0.9,
                 attention_size=16, use_embedding=True, reg="none", lam=None, sparse=False, kwm_lstm_size=20,
                 learning_rate=0.1):
        Model.__init__(self, batch_size, max_len, vocab_size, embeddings_dim, use_embedding,
                       learning_rate=learning_rate)
        self.lstm_size = lstm_size
        self.attention_size = attention_size
        self.reg = reg
        self.lam = lam
        self.kwm_lstm_size = kwm_lstm_size
        self.sparse = sparse
        self.keep_probs = keep_probs
        self.use_alphas = True
        self.build_model()

    def build_model(self):
        rnn_outputs_hypo, final_state_hypo = lstm_layer(self.e_hypo, self.lstm_size, self.batch_size, self.seq_len_hypo, "hypo")
        rnn_outputs_prem, final_state_prem = lstm_layer(self.e_prem, self.lstm_size, self.batch_size, self.seq_len_prem, "prem")

        last_output_hypo, alphas_hypo = attention_layer(self.attention_size, rnn_outputs_hypo, "encoder_hypo", sparse=self.sparse)
        last_output_prem, alphas_prem = attention_layer(self.attention_size, rnn_outputs_prem, "encoder_prem", sparse=self.sparse)
        self.alphas_hypo = alphas_hypo
        self.alphas_prem = alphas_prem
        self.logits = dense_layer(tf.concat([last_output_hypo, last_output_prem], axis=1), 3, activation=None, name="pred_out")
        self.y = tf.nn.softmax(self.logits)

        self.cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(
            labels=tf.one_hot(self.y_holder, depth=3), logits=self.logits))

        self.accuracy = tf.reduce_mean(tf.cast(tf.equal(self.y_holder, tf.argmax(self.y, 1)), tf.float32))
        self.optimizer = tf.train.GradientDescentOptimizer(self.learning_rate)
        self.train_op = self.optimizer.minimize(self.cost)


class MLPPredModel(NLIModel):
    def __init__(self, batch_size=10, max_len=30, lstm_size=20, vocab_size=10000, embeddings_dim=20, keep_probs=0.9,
                 attention_size=16, use_embedding=True, reg="none", lam=None, sparse=False, kwm_lstm_size=20,
                 learning_rate=0.1):
        Model.__init__(self, batch_size, max_len, vocab_size, embeddings_dim, use_embedding,
                       learning_rate=learning_rate)
        self.lstm_size = lstm_size
        self.attention_size = attention_size
        self.reg = reg
        self.lam = lam
        self.kwm_lstm_size = kwm_lstm_size
        self.sparse = sparse
        self.keep_probs = keep_probs
        self.use_alphas = False
        self.build_model()

    def build_model(self):
        inputs_hypo = tf.reshape(self.e_hypo, [-1, self.e_hypo.shape[1] * self.e_hypo.shape[2]])
        inputs_prem = tf.reshape(self.e_prem, [-1, self.e_prem.shape[1] * self.e_prem.shape[2]])

        self.logits = dense_layer(tf.concat([inputs_hypo, inputs_prem], axis=1), 3, activation=None, name="pred_out")

        self.cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(
            labels=tf.one_hot(self.y_holder, depth=3), logits=self.logits))

        self.optimizer = tf.train.GradientDescentOptimizer(self.learning_rate)
        self.train_op = self.optimizer.minimize(self.cost)

        self.y = tf.nn.softmax(self.logits)

        self.accuracy = tf.reduce_mean(tf.cast(tf.equal(self.y_holder, tf.argmax(self.y, 1)), tf.float32))


class LSTMPredModelWithRegAttentionKeyWordModelHEX(NLIModel):
    def __init__(self, batch_size=10, max_len=30, lstm_size=20, vocab_size=10000, embeddings_dim=20, keep_probs=0.9,
                 attention_size=16, use_embedding=True, reg="none", lam=None, sparse=False, kwm_lstm_size=10,
                 learning_rate=0.1):
        Model.__init__(self, batch_size, max_len, vocab_size, embeddings_dim, use_embedding,
                       learning_rate=learning_rate)
        self.lstm_size = lstm_size
        self.attention_size = attention_size
        self.reg = reg
        self.lam = lam
        self.kwm_lstm_size = kwm_lstm_size
        self.sparse = sparse
        self.keep_probs = keep_probs
        self.use_alphas = True
        self.build_model()

    def build_model(self):
        # Define prediction rnn
        rnn_outputs_hypo, final_state_hypo = lstm_layer(self.e_hypo, self.lstm_size, self.batch_size, self.seq_len_hypo, "hypo")
        rnn_outputs_prem, final_state_prem = lstm_layer(self.e_prem, self.lstm_size, self.batch_size, self.seq_len_prem, "prem")

        last_output_hypo, alphas_hypo = attention_layer(self.attention_size, rnn_outputs_hypo, "encoder_hypo", sparse=self.sparse)
        last_output_prem, alphas_prem = attention_layer(self.attention_size, rnn_outputs_prem, "encoder_prem", sparse=self.sparse)
        self.alphas_hypo = alphas_hypo
        self.alphas_prem = alphas_prem
        # last_output = tf.nn.dropout(last_output, self.keep_probs)

        # Define key-word model rnn
        kwm_rnn_outputs_hypo, kwm_final_state_hypo = lstm_layer(self.e_hypo, self.lstm_size, self.batch_size, self.seq_len_hypo, scope="kwm_hypo")
        kwm_rnn_outputs_prem, kwm_final_state_prem = lstm_layer(self.e_prem, self.lstm_size, self.batch_size, self.seq_len_prem, scope="kwm_prem")
        kwm_last_output_hypo, kwm_alphas_hypo = attention_layer(self.attention_size, kwm_rnn_outputs_hypo, "kwm_encoder_hypo", sparse=self.sparse)
        kwm_last_output_prem, kwm_alphas_prem = attention_layer(self.attention_size, kwm_rnn_outputs_prem, "kwm_encoder_prem", sparse=self.sparse)

        last_output = tf.concat([last_output_hypo, last_output_prem], axis=1)
        kwm_last_output = tf.concat([kwm_last_output_hypo, kwm_last_output_prem], axis=1)

        ############################
        # Hex #########################

        h_fc1 = last_output
        h_fc2 = kwm_last_output

        # Hex layer definition
        """
        self.W_cl_1 = tf.Variable(tf.random_normal([self.dim, 3], stddev=0.1))
        self.W_cl_2 = tf.Variable(tf.random_normal([1200, 3]), trainable=True)
        self.b_cl = tf.Variable(tf.random_normal((3,)), trainable=True)
        self.W_cl = tf.concat([self.W_cl_1, self.W_cl_2], 0)
        """

        # Compute prediction using [h_fc1, 0(pad)]
        pad = tf.zeros_like(h_fc2, tf.float32)
        # print(pad.shape) -> (?, 600)

        yconv_contact_pred = tf.nn.dropout(tf.concat([h_fc1, pad], 1), self.keep_probs)

        # y_conv_pred = tf.matmul(yconv_contact_pred, self.W_cl) + self.b_cl
        y_conv_pred = dense_layer(yconv_contact_pred, 3, name="conv_pred")

        self.logits = y_conv_pred  # Prediction

        # Compute loss using [h_fc1, h_fc2] and [0(pad2), h_fc2]
        pad2 = tf.zeros_like(h_fc1, tf.float32)

        yconv_contact_H = tf.concat([pad2, h_fc2], 1)
        # Get Fg
        # y_conv_H = tf.matmul(yconv_contact_H, self.W_cl) + self.b_cl  # get Fg
        y_conv_H = dense_layer(yconv_contact_H, 3, name="conv_H")

        yconv_contact_loss = tf.nn.dropout(tf.concat([h_fc1, h_fc2], 1), self.keep_probs)
        # Get Fb
        # y_conv_loss = tf.matmul(yconv_contact_loss, self.W_cl) + self.b_cl  # get Fb
        y_conv_loss = dense_layer(yconv_contact_loss, 3, name="conv_loss")

        temp = tf.matmul(y_conv_H, y_conv_H, transpose_a=True)
        self.temp = temp

        y_conv_loss = y_conv_loss - tf.matmul(
            tf.matmul(tf.matmul(y_conv_H, tf.matrix_inverse(temp)), y_conv_H, transpose_b=True),
            y_conv_loss)  # get loss

        self.logits = y_conv_loss
        self.y = tf.nn.softmax(self.logits)

        self.cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(
            labels=tf.one_hot(self.y_holder, depth=3), logits=self.logits))

        # Regularize kwm attention
        reg1 = get_reg(kwm_alphas_hypo, lam=self.lam, type=self.reg)
        reg2 = get_reg(kwm_alphas_prem, lam=self.lam, type=self.reg)

        self.cost += reg1 + reg2

        self.optimizer = tf.train.GradientDescentOptimizer(self.learning_rate)
        self.train_op = self.optimizer.minimize(self.cost)
        self.accuracy = tf.reduce_mean(tf.cast(tf.equal(self.y_holder, tf.argmax(self.y, 1)), tf.float32))


