from __future__ import unicode_literals, print_function, division
from io import open
import re
import sys
import getopt
import random
from nltk.translate.bleu_score import sentence_bleu
import torch
import torch.nn as nn
from torch import optim
import torch.nn.functional as F
import warnings
warnings.filterwarnings("ignore")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(device)

SOS_token = 0
EOS_token = 1
MAX_LENGTH = 10

class Lang:
    def __init__(self, name):
        self.name = name
        self.word2index = {}
        self.word2count = {}
        self.index2word = {0: "SOS", 1: "EOS", 3: "UNK"}
        self.n_words = 3  # Count SOS and EOS and UNK

    def addSentence(self, sentence):
        for word in sentence.split(' '):
            self.addWord(word)

    def addWord(self, word):
        if word not in self.word2index:
            self.word2index[word] = self.n_words
            self.word2count[word] = 1
            self.index2word[self.n_words] = word
            self.n_words += 1
        else:
            self.word2count[word] += 1


# Lowercase, trim, and remove non-letter characters


def normalizeString(s):
    s = s.lower().strip()
    s = re.sub(r"([.!?])", r" \1", s)
    s = re.sub(r"([-])", r"", s)
    #s = re.sub(r"[^ёЁа-яА-Яa-zA-Zà-üÀ-Ü0-9.!?]+", r" ", s) #    s = re.sub(r"[^ёЁа-яА-Яa-zA-Zà-üÀ-Ü0-9.!?]+", r" ", s)

    return s


######################################################################
# To read the data file we will split the file into lines, and then split
# lines into pairs. The files are all English → Other Language, so if we
# want to translate from Other Language → English I added the ``reverse``
# flag to reverse the pairs.
#

def readLangs(reverse=False):
    print("Reading lines...")

    # Read the file and split into lines
    # if reverse:
    #     #lines = open('data/OpenSubtitles/processed_OpenSubtitles_reverse.txt', encoding='utf-8').read().strip().split('\n')
    #     lines = open('data/Twitter/processed_Twitter_reverse.txt', encoding='utf-8').read().strip().split('\n')
    # else:
    #     #lines = open('data/OpenSubtitles/processed_OpenSubtitles.txt', encoding='utf-8').read().strip().split('\n')
    lines = open('data/vi_database.txt', encoding='utf-8').read().strip().split('\n')

    # Split every line into pairs and normalize
    pairs = [[normalizeString(s) for s in l.split('\\')] for l in lines]

    # if reverse:
    #     input_lang = Lang('Answer')
    #     output_lang = Lang('Question')
    # else:
    input_lang = Lang('Question')
    output_lang = Lang('Answer')

    return input_lang, output_lang, pairs


######################################################################
# Since there are a *lot* of example sentences and we want to train
# something quickly, we'll trim the data set to only relatively short and
# simple sentences. Here the maximum length is 10 words (that includes
# ending punctuation) and we're filtering to sentences that translate to
# the form "I am" or "He is" etc. (accounting for apostrophes replaced
# earlier).
#

def filterPair(p):
    # if not p:
    #     return False
    # else:
    #     return  len(p[0].split(' ')) < MAX_LENGTH and len(p[1].split(' ')) < MAX_LENGTH
    lst = [x for x in p if len(x.split(' ')) < MAX_LENGTH]
    if len(lst) == 2:
        return True
    else:
        return False


def filterPairs(pairs):
    #tmp =[pair for pair in pairs if filterPair(pair)]
    #lst = filter(lambda pair: filterPair(pair), pairs)
    lst = [None]* len(pairs)
    lst = [pair for pair in pairs if filterPair(pair)]
    return lst



######################################################################
# The full process for preparing the data is:
#
# -  Read text file and split into lines, split lines into pairs
# -  Normalize text, filter by length and content
# -  Make word lists from sentences in pairs
#

def prepareData(reverse=False):
    input_lang, output_lang, pairs = readLangs(reverse)
    print("Read %s sentence pairs" % len(pairs))

    pairs = filterPairs(pairs)
    print("Trimmed to %s sentence pairs" % len(pairs))
    print("Counting words...")
    for pair in pairs:
        input_lang.addSentence(pair[0])
        output_lang.addSentence(pair[1])
    print("Counted words:")
    print(input_lang.name, input_lang.n_words)
    print(output_lang.name, output_lang.n_words)

    return input_lang, output_lang, pairs


input_lang, output_lang, pairs = prepareData(True)
#print(random.choice(pairs))


######################################################################
# The Seq2Seq Model
# =================


class EncoderRNN(nn.Module):
    def __init__(self, input_size, hidden_size):
        super(EncoderRNN, self).__init__()
        self.hidden_size = hidden_size

        self.embedding = nn.Embedding(input_size, hidden_size)
        self.gru = nn.GRU(hidden_size, hidden_size)
        #self.gru_1 = nn.GRU(hidden_size, hidden_size)
        #self.gru_2 = nn.GRU(hidden_size, hidden_size)


    def forward(self, input, hidden):
        embedded = self.embedding(input).view(1, 1, -1)
        output = embedded
        output, hidden = self.gru(output, hidden)
        #output, hidden = self.gru_1(output, hidden)
        #output, hidden = self.gru_2(output, hidden)
        return output, hidden

    def initHidden(self):
        return torch.zeros(1, 1, self.hidden_size, device=device)

######################################################################
# The Decoder
# -----------
#
# The decoder is another RNN that takes the encoder output vector(s) and
# outputs a sequence of words to create the translation.
#


class DecoderRNN(nn.Module):
    def __init__(self, hidden_size, output_size):
        super(DecoderRNN, self).__init__()
        self.hidden_size = hidden_size

        self.embedding = nn.Embedding(output_size, hidden_size)
        self.gru = nn.GRU(hidden_size, hidden_size)
        self.out = nn.Linear(hidden_size, output_size)
        self.softmax = nn.LogSoftmax(dim=1)

    def forward(self, input, hidden):
        output = self.embedding(input).view(1, 1, -1)
        output = F.relu(output)
        output, hidden = self.gru(output, hidden)
        output = self.softmax(self.out(output[0]))
        return output, hidden

    def initHidden(self):
        return torch.zeros(1, 1, self.hidden_size, device=device)

######################################################################
# I encourage you to train and observe the results of this model, but to
# save space we'll be going straight for the gold and introducing the
# Attention Mechanism.
#



class AttnDecoderRNN(nn.Module):
    def __init__(self,hidden_size, output_size,max_length = MAX_LENGTH , dropout_p=0.1):
        super(AttnDecoderRNN, self).__init__()
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.dropout_p = dropout_p
        self.max_length = max_length

        self.embedding = nn.Embedding(self.output_size, self.hidden_size)
        self.attn = nn.Linear(self.hidden_size * 2, self.max_length)
        self.attn_combine = nn.Linear(self.hidden_size * 2, self.hidden_size)
        self.dropout = nn.Dropout(self.dropout_p)
        self.gru = nn.GRU(self.hidden_size, self.hidden_size)
        #self.gru_1 = nn.GRU(self.hidden_size, self.hidden_size)
        #self.gru_2 = nn.GRU(self.hidden_size, self.hidden_size)
        self.out = nn.Linear(self.hidden_size, self.output_size)

    def forward(self, input, hidden, encoder_outputs):
        embedded = self.embedding(input).view(1, 1, -1)
        embedded = self.dropout(embedded)

        attn_weights = F.softmax(
            self.attn(torch.cat((embedded[0], hidden[0]), 1)), dim=1)
        # print(attn_weights.size())
        # print(encoder_outputs.size())
        attn_applied = torch.bmm(attn_weights.unsqueeze(0),
                                 encoder_outputs.unsqueeze(0))

        output = torch.cat((embedded[0], attn_applied[0]), 1)
        output = self.attn_combine(output).unsqueeze(0)

        output = F.relu(output)
        output, hidden = self.gru(output, hidden)
        #output, hidden = self.gru_1(output, hidden)
        #output, hidden = self.gru_2(output, hidden)

        output = F.log_softmax(self.out(output[0]), dim=1)
        return output, hidden, attn_weights

    def initHidden(self):
        return torch.zeros(1, 1, self.hidden_size, device=device)


######################################################################
# .. note:: There are other forms of attention that work around the length
#   limitation by using a relative position approach. Read about "local
#   attention" in `Effective Approaches to Attention-based Neural Machine
#   Translation <https://arxiv.org/abs/1508.04025>`__.
#
# Training
# ========
#
# Preparing Training Data
# -----------------------
#
# To train, for each pair we will need an input tensor (indexes of the
# words in the input sentence) and target tensor (indexes of the words in
# the target sentence). While creating these vectors we will append the
# EOS token to both sequences.
#

def indexesFromSentence(lang, sentence):
    return [lang.word2index[word] if word in lang.word2index.keys() else lang.word2index['UNK'] for word in sentence.split(' ')]


def tensorFromSentence(lang, sentence):
    indexes = indexesFromSentence(lang, sentence)
    indexes.append(EOS_token)
    return torch.tensor(indexes, dtype=torch.long, device=device).view(-1, 1)


def tensorsFromPair(pair):
    input_tensor = tensorFromSentence(input_lang, pair[0])
    target_tensor = tensorFromSentence(output_lang, pair[1])
    return (input_tensor, target_tensor)


######################################################################
# Training the Model
# ------------------


teacher_forcing_ratio = 0.5


def train(input_tensor, target_tensor, encoder, decoder, encoder_optimizer, decoder_optimizer, criterion, max_length=MAX_LENGTH):
    encoder_hidden = encoder.initHidden()

    encoder_optimizer.zero_grad()
    decoder_optimizer.zero_grad()

    input_length = input_tensor.size(0)
    target_length = target_tensor.size(0)

    encoder_outputs = torch.zeros(max_length, encoder.hidden_size, device=device)

    loss = 0

    for ei in range(input_length):
        encoder_output, encoder_hidden = encoder(
            input_tensor[ei], encoder_hidden)
        encoder_outputs[ei] = encoder_output[0, 0]

    decoder_input = torch.tensor([[SOS_token]], device=device)

    decoder_hidden = encoder_hidden

    use_teacher_forcing = True if random.random() < teacher_forcing_ratio else False

    if use_teacher_forcing:
        # Teacher forcing: Feed the target as the next input
        for di in range(target_length):
            decoder_output, decoder_hidden, decoder_attention = decoder(
                decoder_input, decoder_hidden, encoder_outputs)
            loss += criterion(decoder_output, target_tensor[di])
            decoder_input = target_tensor[di]  # Teacher forcing

    else:
        # Without teacher forcing: use its own predictions as the next input
        for di in range(target_length):
            decoder_output, decoder_hidden, decoder_attention = decoder(
                decoder_input, decoder_hidden, encoder_outputs)
            topv, topi = decoder_output.topk(1)
            decoder_input = topi.squeeze().detach()  # detach from history as input

            loss += criterion(decoder_output, target_tensor[di])
            if decoder_input.item() == EOS_token:
                break

    loss.backward()

    encoder_optimizer.step()
    decoder_optimizer.step()

    return loss.item() / target_length


######################################################################
# This is a helper function to print time elapsed and estimated time
# remaining given the current time and progress %.
#

import time
import math


def asMinutes(s):
    m = math.floor(s / 60)
    s -= m * 60
    return '%dm %ds' % (m, s)


def timeSince(since, percent):
    now = time.time()
    s = now - since
    es = s / (percent)
    rs = es - s
    return '%s (- %s)' % (asMinutes(s), asMinutes(rs))


######################################################################
# The whole training process looks like this:
#
# -  Start a timer
# -  Initialize optimizers and criterion
# -  Create set of training pairs
# -  Start empty losses array for plotting
#
# Then we call ``train`` many times and occasionally print the progress (%
# of examples, time so far, estimated time) and average loss.
#

def trainIters(encoder, decoder, n_iters, print_every=1000, plot_every=100, learning_rate=0.001): # lr =0.01 -> 0.001 -> 0.0005
    start = time.time()
    plot_losses = []
    all_losses = [] # Use to calculate perplexity
    print_loss_total = 0  # Reset every print_every
    plot_loss_total = 0  # Reset every plot_every

    encoder_optimizer = optim.Adam(encoder.parameters(), lr=learning_rate) #SGD , weight_decay=1e-6
    decoder_optimizer = optim.Adam(decoder.parameters(), lr=learning_rate) #SGD , weight_decay=1e-6
    #training_pairs = [tensorsFromPair(random.choice(pairs)) for i in range(n_iters)]
    criterion = nn.NLLLoss()

    for iter in range(1, n_iters + 1):
        training_pair = tensorsFromPair(random.choice(pairs)) #training_pairs[iter - 1]
        input_tensor = training_pair[0]
        target_tensor = training_pair[1]

        loss = train(input_tensor, target_tensor, encoder,
                     decoder, encoder_optimizer, decoder_optimizer, criterion)
        all_losses.append(loss)
        print_loss_total += loss
        plot_loss_total += loss

        if iter % print_every == 0:
            print_loss_avg = print_loss_total / print_every
            print_loss_total = 0
            print('%s (%d %d%%) %.4f' % (timeSince(start, iter / n_iters),
                                         iter, iter / n_iters * 100, print_loss_avg))
            torch.save(encoder, 'model/VI-model/encoder.pkl')
            torch.save(decoder, 'model/VI-model/decoder.pkl')

        if iter % plot_every == 0:
            plot_loss_avg = plot_loss_total / plot_every
            plot_losses.append(plot_loss_avg)
            plot_loss_total = 0

        perplexity = 2 ** (np.mean(all_losses)) # Not sure if the formular is correct, base =2 or e?

    showPlot(plot_losses)
    return perplexity


######################################################################
# Plotting results
# ----------------
#
# Plotting is done with matplotlib, using the array of loss values
# ``plot_losses`` saved while training.
#

import matplotlib.pyplot as plt
plt.switch_backend('agg')
import matplotlib.ticker as ticker
import numpy as np


def showPlot(points):
    plt.figure()
    fig, ax = plt.subplots()
    # this locator puts ticks at regular intervals
    loc = ticker.MultipleLocator(base=0.2)
    ax.yaxis.set_major_locator(loc)
    plt.plot(points)


######################################################################
# Evaluation
# ==========
#
# Evaluation is mostly the same as training, but there are no targets so
# we simply feed the decoder's predictions back to itself for each step.
# Every time it predicts a word we add it to the output string, and if it
# predicts the EOS token we stop there. We also store the decoder's
# attention outputs for display later.
#

def evaluate(encoder, decoder, sentence, max_length=MAX_LENGTH):
    with torch.no_grad():
        input_tensor = tensorFromSentence(input_lang, sentence)
        if input_tensor.size()[0] > 50:
            input_tensor = input_tensor[:50]
        input_length = input_tensor.size()[0]
        encoder_hidden = encoder.initHidden()

        encoder_outputs = torch.zeros(max_length, encoder.hidden_size, device=device)

        for ei in range(input_length):
            encoder_output, encoder_hidden = encoder(input_tensor[ei],
                                                     encoder_hidden)
            encoder_outputs[ei] += encoder_output[0, 0]

        decoder_input = torch.tensor([[SOS_token]], device=device)  # SOS

        decoder_hidden = encoder_hidden

        decoded_words = []
        decoder_attentions = torch.zeros(max_length, max_length)

        for di in range(max_length):
            decoder_output, decoder_hidden, decoder_attention = decoder(
                decoder_input, decoder_hidden, encoder_outputs)
            decoder_attentions[di] = decoder_attention.data
            topv, topi = decoder_output.data.topk(1)
            if topi.item() == EOS_token:
                decoded_words.append('<EOS>')
                break
            else:
                decoded_words.append(output_lang.index2word[topi.item()])

            decoder_input = topi.squeeze().detach()

        return decoded_words[:-1], decoder_attentions[:di + 1]


######################################################################
# We can evaluate random sentences from the training set and print out the
# input, target, and output to make some subjective quality judgements:
#

def evaluateRandomly(encoder, decoder, n=10):
    for i in range(n):
        pair = random.choice(pairs)
        print('>', pair[0])
        print('=', pair[1])
        output_words, attentions = evaluate(encoder, decoder, pair[0])
        output_sentence = ' '.join(output_words)
        print('<', output_sentence)
        print('')


######################################################################
# Training and Evaluating
# =======================
#
# With all these helper functions in place (it looks like extra work, but
# it makes it easier to run multiple experiments) we can actually
# initialize a network and start training.
#
# Remember that the input sentences were heavily filtered. For this small
# dataset we can use relatively small networks of 256 hidden nodes and a
# single GRU layer. After about 40 minutes on a MacBook CPU we'll get some
# reasonable results.
#
# .. Note::
#    If you run this notebook you can train, interrupt the kernel,
#    evaluate, and continue training later. Comment out the lines where the
#    encoder and decoder are initialized and run ``trainIters`` again.
#

def run_train(iterations):
    hidden_size = 256 # original 256 for single layer
    try:
        encoder1 = torch.load('model/VI-model/encoder.pkl')
        attn_decoder1 = torch.load('model/VI-model/decoder.pkl')
    except:
        encoder1 = EncoderRNN(input_lang.n_words, hidden_size).to(device)
        attn_decoder1 = AttnDecoderRNN(hidden_size, output_lang.n_words, dropout_p=0.1).to(device)

    perplexity = trainIters(encoder1, attn_decoder1, iterations, print_every=500, learning_rate=0.000001) #5000
    evaluateRandomly(encoder1, attn_decoder1)
    return perplexity, encoder1, attn_decoder1


######################################################################
# Visualizing Attention
# ---------------------
#
# A useful property of the attention mechanism is its highly interpretable
# outputs. Because it is used to weight specific encoder outputs of the
# input sequence, we can imagine looking where the network is focused most
# at each time step.
#
# You could simply run ``plt.matshow(attentions)`` to see attention output
# displayed as a matrix, with the columns being input steps and rows being
# output steps:
#

    output_words, attentions = evaluate(
        encoder1, attn_decoder1, u"﻿привет")
    plt.matshow(attentions.numpy())
    return encoder1, attn_decoder1


######################################################################
# For a better viewing experience we will do the extra work of adding axes
# and labels:
#

def showAttention(input_sentence, output_words, attentions):
    # Set up figure with colorbar
    fig = plt.figure()
    ax = fig.add_subplot(111)
    cax = ax.matshow(attentions.numpy(), cmap='bone')
    fig.colorbar(cax)

    # Set up axes
    ax.set_xticklabels([''] + input_sentence.split(' ') +
                       ['<EOS>'], rotation=90)
    ax.set_yticklabels([''] + output_words)

    # Show label at every tick
    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))

    plt.show()
    fig.savefig("viatt.png")


def evaluateAndShowAttention(input_sentence, encoder1, attn_decoder1):
    output_words, attentions = evaluate(
        encoder1, attn_decoder1, input_sentence)
    print('input =', input_sentence)
    print('output =', ' '.join(output_words))
    showAttention(input_sentence, output_words, attentions)

def evaluateAndReturnResponse(input_sentence, encoder1, attn_decoder1):
    output_words, attentions = evaluate(
        encoder1, attn_decoder1, input_sentence)
    output = ' '.join(output_words)
    return output


def calculate_BLEU(encoder1, attn_decoder1, n_examples):
    total_score = 0
    evaluate_pairs = [random.choice(pairs) for i in range(n_examples)]
    for pair in evaluate_pairs:
        input_sentence = pair[0]
        target_words = [pair[1]]
        output_words, _ = evaluate(encoder1, attn_decoder1, input_sentence)
        output_words = output_words
        score = sentence_bleu(target_words, output_words)
        total_score += score
    average_BLEU = total_score/len(pairs)
    return average_BLEU


#evaluateAndShowAttention("elle a cinq ans de moins que moi .")
if __name__ == '__main__':

    # try:
    #     opts, args = getopt.getopt(sys.argv[1:], "ui:", ["usage=", "iters="])
    # except getopt.GetoptError:
    #     sys.exit()
    # iters = 150000
    # for opt, arg in opts:
    #     if opt == "--usage":
    #         usage = arg
    #     if opt == "--iters":
    #         iters = arg
    # to train a chatbot

    perplexity, _, _ = run_train(iterations=150000) #75000
    print('Perplexity: ', perplexity)

    # elif usage == 'evaluate':
    #     # calculate BLEU and perplexity
    perplexity, encoder1, attn_decoder1 = run_train(iterations= 500) # 500 samples perplexity: 4.58290114593
    print('Perplexity of the whole training process: ', perplexity)
    BLEU = calculate_BLEU(encoder1, attn_decoder1, 5000) # 5000 samples BLEU score: 0.3024%
    print('BLEU score of the whole model: {:.4%}'.format(BLEU))

    # elif usage == 'test':
        # to test a chatbot
    encoder1 = torch.load('model/VI-model/encoder.pkl')
    attn_decoder1 = torch.load('model/VI-model/decoder.pkl')

    input_sentence = ''
    while input_sentence != 'exit':
        input_sentence = normalizeString(input('User input: '))
        output_sentence = evaluateAndReturnResponse(input_sentence, encoder1, attn_decoder1)
        print('Agent: ', output_sentence)

    evaluateAndShowAttention("cháu học lớp mấy rồi?",encoder1,attn_decoder1)

## for 1 layer encoder and decoder with OpenSubtitle Dataset (hidden_size = 256)
# 500 samples perplexity: 4.58290114593
# 5000 samples BLEU score: 0.3024%


## for 1 layer encoder and decoder with Twitter Triplet Dataset (hidden_size = 512)
# Perplexity of the whole training process:  2.65806118166
# BLEU score of the whole model: 2.1589%