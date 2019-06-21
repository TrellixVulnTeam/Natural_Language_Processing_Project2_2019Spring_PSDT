# coding=utf-8
# Copyright 2018 The Google AI Language Team Authors and The HuggingFace Inc. team.
# Copyright (c) 2018, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#	 http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""BERT finetuning runner."""

from __future__ import absolute_import, division, print_function

import argparse
import csv
import logging
import os
import random
import sys
import re
import pandas as pd
import numpy as np
import torch
from torch.utils.data import (DataLoader, RandomSampler, SequentialSampler,
							  TensorDataset)
from torch.utils.data.distributed import DistributedSampler
from tqdm import tqdm, trange

from torch.nn import CrossEntropyLoss, MSELoss, NLLLoss
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import matthews_corrcoef, f1_score

from pytorch_pretrained_bert.file_utils import PYTORCH_PRETRAINED_BERT_CACHE, WEIGHTS_NAME, CONFIG_NAME
from pytorch_pretrained_bert.modeling import BertForSequenceClassification, BertConfig
from pytorch_pretrained_bert.tokenization import BertTokenizer
from pytorch_pretrained_bert.optimization import BertAdam, warmup_linear

logger = logging.getLogger(__name__)


class InputExample(object):
	"""A single training/test example for simple sequence classification."""

	def __init__(self, guid, text_a, text_b=None, label=None):
		"""Constructs a InputExample.

		Args:
			guid: Unique id for the example.
			text_a: string. The untokenized text of the first sequence. For single
			sequence tasks, only this sequence must be specified.
			text_b: (Optional) string. The untokenized text of the second sequence.
			Only must be specified for sequence pair tasks.
			label: (Optional) string. The label of the example. This should be
			specified for train and dev examples, but not for test examples.
		"""
		self.guid = guid
		self.text_a = text_a
		self.text_b = text_b
		self.label = label


class InputFeatures(object):
	"""A single set of features of data."""

	def __init__(self,guid, input_ids, input_mask, segment_ids, label_id):
		self.guid = guid
		self.input_ids = input_ids
		self.input_mask = input_mask
		self.segment_ids = segment_ids
		self.label_id = label_id

class DataProcessor(object):
	"""Base class for data converters for sequence classification data sets."""

	def get_train_examples(self, data_dir):
		"""Gets a collection of `InputExample`s for the train set."""
		raise NotImplementedError()

	def get_dev_examples(self, data_dir):
		"""Gets a collection of `InputExample`s for the dev set."""
		raise NotImplementedError()

	def get_labels(self):
		"""Gets the list of labels for this data set."""
		raise NotImplementedError()

	@classmethod
	def _read_tsv(cls, input_file, quotechar=None):
		"""Reads a tab separated value file."""
		with open(input_file, "r", encoding="utf-8") as f:
			reader = csv.reader(f, delimiter="\t", quotechar=quotechar)
			lines = []
			for line in reader:
				if sys.version_info[0] == 2:
					line = list(unicode(cell, 'utf-8') for cell in line)
				lines.append(line)
			return lines

def remove_emoji(sen):
	sen = str(sen).lower()
	temp = ['']
	for word in sen.strip().split():
		if(temp[-1] == '@user' and word == '@user'):
			continue
		if(word[0]=='#'):
			continue
		temp.append(word)
	
	sen = ' '.join(temp[1:])
	"""
	emoji_pattern = re.compile("["	
	u"\U0001F600-\U0001F64F"  # emoticons
	u"\U0001F300-\U0001F5FF"  # symbols & pictographs
	u"\U0001F680-\U0001F6FF"  # transport & map symbols
	u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
	u"\U00002702-\U000027B0"
	u"\U000024C2-\U0001F251"
	"]+", flags=re.UNICODE)
	
	sen = emoji_pattern.sub(r'', sen)
	sen = re.sub(r'[\u3000-\u303F]', '', sen)
	sen = re.sub(r'[\u3000-\u303F]', '', sen)
	sen = re.sub(r'[\uFF00-\uFFEF]', '', sen)
	
	emoji = '💕' + '🤘' + '👯' + '🏋️' + '🚗🚗' + '💪' + '🎄' + '🔁' + '👋' + '💪💪' + '🔥' + \
	'😝👶🏻☀️🍹' + '🔁' + '✨👯' + '🌞' + '💖' + '🎉✨' + '🔁' + '🌸' + '❤️💛💚💙💜' + \
	'🇫🇷' + '🎆' + '💋' + '🔁' + '👂' + '🎸' + '💦💦' + '💦💦' + '❤' + '🍷' + \
	'🎂' + '👫' + '🌞' + '🌊' + '🍁' + '🔁' + '🎶' + '🌹🌹' + '😆' +'🐔' + '🤠🇹🇭' + \
	'👯' + '🌙' + '🎄' + '🎤' + '🔥🔥' + '🔥🔥' + '📚' + '💕' + '🙋' + '😁👾🍸' + '🔥' + \
	'🎓' + '🍷' + '✏️🍍🍎✏️' + '💧' + '🔁' + '🌞' + '🛋' + '🔁' + '💪🏼' + '💔' + \
	'🔁' + '🏆' + '🏆' + '🔁' + '🎉' + '🎉' + '🏃👟' + '🍖🍷🍾' + '❤️' + '🔁' + '😢' + \
	'👋🏼' + '👂' + '🗽' + '🇵🇷' + '🎸' + '🔁' + '🌧' + '🔁' + '🍿🍿' + '❤️' + '😈' + \
	'😈' + '🇭🇰' + '🌞' + '🌞' + '😜' + '👊' + '🇺🇸' + '😂' + '🤔' + ''
	
	for c in emoji:
		sen = sen.replace(c, '')
	"""
	noises = ['url', '\'ve', 'n\'t', '\'s', '\'m']
	sen = sen.replace('url', '')
	sen = sen.replace('\'ve', ' have')
	sen = sen.replace('\'m', ' am')
	#sen = sen.replace('@user', '')
	sen = sen.replace('@user', '@')
	
	return sen

class SemevalProcessor(DataProcessor):
	"""Processor for the WNLI data set (GLUE version)."""
	def get_train_examples(self, data_dir):
		"""See base class."""
		return self._create_examples(
			pd.read_csv(os.path.join(data_dir, "train.tsv"), sep='\t'), "train")

	def get_dev_examples(self, data_dir):
		"""See base class."""
		return self._create_examples(
			pd.read_csv(os.path.join(data_dir, "valid.tsv"), sep='\t'), "train")

	def get_test_examples(self, file_name):
		"""See base class."""
		data = pd.read_csv(file_name, sep='\t')
		#OFF	UNT	NULL
		data['subtask_a'] = pd.Series(['OFF']*data.shape[0], index=data.index)
		data['subtask_b'] = pd.Series(['UNT']*data.shape[0], index=data.index)
		data['subtask_c'] = pd.Series(['NULL']*data.shape[0], index=data.index)
		return self._create_examples(data, "test")
			

	def get_labels(self):
		"""See base class."""
		return [
			['NOT', 'OFF'],
			['NULL', 'UNT', 'TIN'],
			['NULL', 'OTH', 'GRP', 'IND']
		]

	def _create_examples(self, data, set_type):
		"""Creates examples for the training and dev sets."""
		#id	tweet	subtask_a	subtask_b	subtask_c
		ids = data['id'].tolist()
		texts = data['tweet'].tolist()
		label_as = data['subtask_a'].tolist()
		label_bs = data['subtask_b'].fillna('NULL').tolist()
		label_cs = data['subtask_c'].fillna('NULL').tolist()

		examples = []
		#id,tid1,tid2,title1_zh,title2_zh,title1_en,title2_en,label
		for i,(guid,text,label_a,label_b,label_c) in enumerate( zip(ids,texts,label_as,label_bs,label_cs)):
			label = [label_a,label_b,label_c]
			text = remove_emoji(text)
			examples.append(InputExample(guid=guid, text_a=text, label=label))

			
		return examples


def convert_examples_to_features(examples, label_lists, max_seq_length,
								 tokenizer, output_mode):
	"""Loads a data file into a list of `InputBatch`s."""
	if(output_mode == "multi_classification"):
		"""
		['OFF', 'NOT'],
		['NULL', 'UNT', 'TIN'],
		['NULL', 'OTH', 'GRP', 'IND']
		"""
		label_map = []	
		label_map.append( {'NOT':0,'OFF':1} )
		label_map.append( {'NULL':0, 'UNT':0, 'TIN':1} )
		label_map.append( {'NULL':0, 'OTH':0, 'GRP':1, 'IND':2} )

	else:
		label_map =  {label : i for i, label in enumerate(label_list)} 

	features = []
	for (ex_index, example) in enumerate(examples):
		if ex_index % 100000 == 0:
			logger.info("Writing example %d of %d" % (ex_index, len(examples)))

		tokens_a = tokenizer.tokenize(example.text_a)

		tokens_b = None
		if example.text_b:
			tokens_b = tokenizer.tokenize(example.text_b)
			# Modifies `tokens_a` and `tokens_b` in place so that the total
			# length is less than the specified length.
			# Account for [CLS], [SEP], [SEP] with "- 3"
			tokens_a,tokens_b = _truncate_seq_pair(tokens_a, tokens_b, max_seq_length - 3)
		else:
			# Account for [CLS] and [SEP] with "- 2"
			if len(tokens_a) > max_seq_length - 2:
				tokens_a = tokens_a[:(max_seq_length - 2)]

		# The convention in BERT is:
		# (a) For sequence pairs:
		#  tokens:   [CLS] is this jack ##son ##ville ? [SEP] no it is not . [SEP]
		#  type_ids: 0   0  0	0	0	 0	   0 0	1  1  1  1   1 1
		# (b) For single sequences:
		#  tokens:   [CLS] the dog is hairy . [SEP]
		#  type_ids: 0   0   0   0  0	 0 0
		#
		# Where "type_ids" are used to indicate whether this is the first
		# sequence or the second sequence. The embedding vectors for `type=0` and
		# `type=1` were learned during pre-training and are added to the wordpiece
		# embedding vector (and position vector). This is not *strictly* necessary
		# since the [SEP] token unambiguously separates the sequences, but it makes
		# it easier for the model to learn the concept of sequences.
		#
		# For classification tasks, the first vector (corresponding to [CLS]) is
		# used as as the "sentence vector". Note that this only makes sense because
		# the entire model is fine-tuned.
		tokens = ["[CLS]"] + tokens_a + ["[SEP]"]
		segment_ids = [0] * len(tokens)

		if tokens_b:
			tokens += tokens_b + ["[SEP]"]
			segment_ids += [1] * (len(tokens_b) + 1)

		input_ids = tokenizer.convert_tokens_to_ids(tokens)

		# The mask has 1 for real tokens and 0 for padding tokens. Only real
		# tokens are attended to.
		input_mask = [1] * len(input_ids)

		# Zero-pad up to the sequence length.
		padding = [0] * (max_seq_length - len(input_ids))
		input_ids += padding
		input_mask += padding
		segment_ids += padding

		assert len(input_ids) == max_seq_length
		assert len(input_mask) == max_seq_length
		assert len(segment_ids) == max_seq_length

		if(output_mode == "multi_classification"):
			label = []
			for i,label_m in enumerate(label_map):
				label.append( label_m[example.label[i]] )

		elif output_mode == "classification":
			label = label_map[example.label]

		elif output_mode == "regression":
			label = float(example.label)
		else:
			raise KeyError(output_mode)

		if ex_index > 22 and ex_index < 29:
			logger.info("*** Example ***")
			logger.info("guid: %s" % (example.guid))
			logger.info("tokens: %s" % " ".join([str(x) for x in tokens]))
			logger.info("ori: {0} {1}".format([example.text_a], [example.text_b]))
			logger.info("input_ids: %s" % " ".join([str(x) for x in input_ids]))
			logger.info("input_mask: %s" % " ".join([str(x) for x in input_mask]))
			logger.info("segment_ids: %s" % " ".join([str(x) for x in segment_ids]))
			logger.info("label: {0} (id = {1})".format(example.label, label))

		features.append(
				InputFeatures(guid=example.guid,
							  input_ids=input_ids,
							  input_mask=input_mask,
							  segment_ids=segment_ids,
							  label_id=label))
	return features


def _truncate_seq_pair(tokens_a, tokens_b, max_length):
	"""Truncates a sequence pair in place to the maximum length."""

	# This is a simple heuristic which will always truncate the longer sequence
	# one token at a time. This makes more sense than truncating an equal percent
	# of tokens from each, since if one sequence is very short then each token
	# that's truncated likely contains more information than a longer sequence.
		
	if(len(tokens_a)+len(tokens_b)>max_length):
	    if(len(tokens_a)>=max_length/2 and len(tokens_b)>=max_length/2):
	        tokens_a = tokens_a[:max_length//2]
	        tokens_b = tokens_b[:max_length//2]
	    elif(len(tokens_a)>len(tokens_b)):
	        tokens_a = tokens_a[:max_length-len(tokens_b)]
	    else:
	        tokens_b = tokens_b[:max_length-len(tokens_a)]
	
	return tokens_a,tokens_b


def simple_accuracy(preds, labels):
	return (preds == labels).astype(int).mean()

def multi_acc_and_f1(preds, labels):
	# convert pred to label
	out = []

	pred = np.array(preds[0][0]).argmax(axis=-1)
	label=labels[:,0]

	acc = simple_accuracy(	pred,label	)
	f1 = f1_score(y_true=label, y_pred=pred,average='macro')
	out.append({
		"acc": acc,
		"f1": f1,
	})

	pred = []
	label = []		
	for p,l in zip( np.array(preds[1][0]),labels):
		if(l[0]==0):
			continue
		pred.append(p.argmax(axis=-1))
		label.append(l[1])
	pred = np.array(pred)
	label = np.array(label)
	acc = simple_accuracy(pred,label)
	f1 = f1_score(y_true=label, y_pred=pred,average='macro')
	out.append({
		"acc": acc,
		"f1": f1,
	})
	
	pred = []
	label = []		
	for p,l in zip( np.array(preds[2][0]),labels):
		if(l[1]==0):
			continue
		pred.append(p.argmax(axis=-1))
		label.append(l[2])
	pred = np.array(pred)
	label = np.array(label)
	acc = simple_accuracy(pred,label)
	f1 = f1_score(y_true=label, y_pred=pred,average='macro')
	out.append({
		"acc": acc,
		"f1": f1,
	})

	return out





def compute_metrics(task_name, preds, labels):
	if task_name == "semeval":
		return  {'total':multi_acc_and_f1(preds, labels)}
	else:
		raise KeyError(task_name)


def main():
	parser = argparse.ArgumentParser()

	## Required parameters
	parser.add_argument("--data_dir",
						default=None,
						type=str,
						required=True,
						help="The input data dir. Should contain the .tsv files (or other data files) for the task.")
	parser.add_argument("--bert_model", default=None, type=str, required=True,
						help="Bert pre-trained model selected in the list: bert-base-uncased, "
						"bert-large-uncased, bert-base-cased, bert-large-cased, bert-base-multilingual-uncased, "
						"bert-base-multilingual-cased, bert-base-chinese.")
	parser.add_argument("--task_name",
						default=None,
						type=str,
						required=True,
						help="The name of the task to train.")
	parser.add_argument("--test_task",
						default='taska',
						type=str,
						help="The task to output.")
	parser.add_argument("--output_dir",
						default=None,
						type=str,
						required=True,
						help="The output directory where the model predictions and checkpoints will be written.")

	## Other parameters
	parser.add_argument("--cache_dir",
						default="",
						type=str,
						help="Where do you want to store the pre-trained models downloaded from s3")
	parser.add_argument("--max_seq_length",
						default=80,
						type=int,
						help="The maximum total input sequence length after WordPiece tokenization. \n"
							 "Sequences longer than this will be truncated, and sequences shorter \n"
							 "than this will be padded.")
	parser.add_argument("--do_train",
						action='store_true',
						help="Whether to run training.")
	parser.add_argument("--do_eval",
						action='store_true',
						help="Whether to run eval on the dev set.")
	parser.add_argument("--do_test",
						action='store_true',
						help="Whether to run test on the test set.")
	parser.add_argument("--do_lower_case",
						action='store_true',
						help="Set this flag if you are using an uncased model.")
	parser.add_argument("--train_batch_size",
						default=128,
						type=int,
						help="Total batch size for training.")
	parser.add_argument("--eval_batch_size",
						default=64,
						type=int,
						help="Total batch size for eval.")
	parser.add_argument("--learning_rate",
						default=1e-6,
						type=float,
						help="The initial learning rate for Adam.")
	parser.add_argument("--num_train_epochs",
						default=3.0,
						type=float,
						help="Total number of training epochs to perform.")
	parser.add_argument("--warmup_proportion",
						default=0.1,
						type=float,
						help="Proportion of training to perform linear learning rate warmup for. "
							 "E.g., 0.1 = 10%% of training.")
	parser.add_argument("--no_cuda",
						action='store_true',
						help="Whether not to use CUDA when available")
	parser.add_argument("--local_rank",
						type=int,
						default=-1,
						help="local_rank for distributed training on gpus")
	parser.add_argument('--seed',
						type=int,
						default=42,
						help="random seed for initialization")
	parser.add_argument('--gradient_accumulation_steps',
						type=int,
						default=2,
						help="Number of updates steps to accumulate before performing a backward/update pass.")
	parser.add_argument('--fp16',
						action='store_true',
						help="Whether to use 16-bit float precision instead of 32-bit")
	parser.add_argument('--loss_scale',
						type=float, default=0,
						help="Loss scaling to improve fp16 numeric stability. Only used when fp16 set to True.\n"
							 "0 (default value): dynamic loss scaling.\n"
							 "Positive power of 2: static loss scaling value.\n")
	parser.add_argument('--server_ip', type=str, default='', help="Can be used for distant debugging.")
	parser.add_argument('--server_port', type=str, default='', help="Can be used for distant debugging.")
	args = parser.parse_args()

	if args.server_ip and args.server_port:
		# Distant debugging - see https://code.visualstudio.com/docs/python/debugging#_attach-to-a-local-script
		import ptvsd
		print("Waiting for debugger attach")
		ptvsd.enable_attach(address=(args.server_ip, args.server_port), redirect_output=True)
		ptvsd.wait_for_attach()

	if args.local_rank == -1 or args.no_cuda:
		device = torch.device("cuda" if torch.cuda.is_available() and not args.no_cuda else "cpu")
		n_gpu = torch.cuda.device_count()
	else:
		torch.cuda.set_device(args.local_rank)
		device = torch.device("cuda", args.local_rank)
		n_gpu = 1
		# Initializes the distributed backend which will take care of sychronizing nodes/GPUs
		torch.distributed.init_process_group(backend='nccl')

	logging.basicConfig(format = '%(asctime)s - %(levelname)s - %(name)s -   %(message)s',
						datefmt = '%m/%d/%Y %H:%M:%S',
						level = logging.INFO if args.local_rank in [-1, 0] else logging.WARN)

	logger.info("device: {} n_gpu: {}, distributed training: {}, 16-bits training: {}".format(
		device, n_gpu, bool(args.local_rank != -1), args.fp16))

	if args.gradient_accumulation_steps < 1:
		raise ValueError("Invalid gradient_accumulation_steps parameter: {}, should be >= 1".format(
							args.gradient_accumulation_steps))

	args.train_batch_size = args.train_batch_size // args.gradient_accumulation_steps

	random.seed(args.seed)
	np.random.seed(args.seed)
	torch.manual_seed(args.seed)
	if n_gpu > 0:
		torch.cuda.manual_seed_all(args.seed)

	if not args.do_train and not args.do_eval and not args.do_test:
		raise ValueError("At least one of `do_train` or `do_eval` must be True.")

	if os.path.exists(args.output_dir) and os.listdir(args.output_dir) and args.do_train:
		raise ValueError("Output directory ({}) already exists and is not empty.".format(args.output_dir))
	if not os.path.exists(args.output_dir):
		os.makedirs(args.output_dir)

	task_name = args.task_name.lower()


	processor = SemevalProcessor()
	output_mode = "multi_classification"

	label_list = processor.get_labels()
	
	if(output_mode == "multi_classification"):
		num_labels = []
		for l in label_list:
			num_labels.append( len(l) )
		num_labels[1]-=1
		num_labels[2]-=1

	else:
		num_labels = len(label_list)

	tokenizer = BertTokenizer.from_pretrained(args.bert_model, do_lower_case=args.do_lower_case)

	train_examples = None
	num_train_optimization_steps = None
	if args.do_train:
		train_examples = processor.get_train_examples(args.data_dir)
		num_train_optimization_steps = int(
			len(train_examples) / args.train_batch_size / args.gradient_accumulation_steps) * args.num_train_epochs
		if args.local_rank != -1:
			num_train_optimization_steps = num_train_optimization_steps // torch.distributed.get_world_size()

	# Prepare model
	cache_dir = args.cache_dir if args.cache_dir else os.path.join(str(PYTORCH_PRETRAINED_BERT_CACHE), 'distributed_{}'.format(args.local_rank))
	model = BertForSequenceClassification.from_pretrained(args.bert_model,
			  cache_dir=cache_dir,
			  num_labels=num_labels)
	if args.fp16:
		model.half()
	model.to(device)
	if args.local_rank != -1:
		try:
			from apex.parallel import DistributedDataParallel as DDP
		except ImportError:
			raise ImportError("Please install apex from https://www.github.com/nvidia/apex to use distributed and fp16 training.")

		model = DDP(model)
	elif n_gpu > 1:
		model = torch.nn.DataParallel(model)

	# Prepare optimizer
	param_optimizer = list(model.named_parameters())
	no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
	optimizer_grouped_parameters = [
		{'params': [p for n, p in param_optimizer if not any(nd in n for nd in no_decay)], 'weight_decay': 0.01},
		{'params': [p for n, p in param_optimizer if any(nd in n for nd in no_decay)], 'weight_decay': 0.0}
		]
	if args.fp16:
		try:
			from apex.optimizers import FP16_Optimizer
			from apex.optimizers import FusedAdam
		except ImportError:
			raise ImportError("Please install apex from https://www.github.com/nvidia/apex to use distributed and fp16 training.")

		optimizer = FusedAdam(optimizer_grouped_parameters,
							  lr=args.learning_rate,
							  bias_correction=False,
							  max_grad_norm=1.0)
		if args.loss_scale == 0:
			optimizer = FP16_Optimizer(optimizer, dynamic_loss_scale=True)
		else:
			optimizer = FP16_Optimizer(optimizer, static_loss_scale=args.loss_scale)

	else:
		optimizer = BertAdam(optimizer_grouped_parameters,
							 lr=args.learning_rate,
							 warmup=args.warmup_proportion,
							 t_total=num_train_optimization_steps)

	global_step = 0
	nb_tr_steps = 0
	tr_loss = 0
	if args.do_train:
		train_features = convert_examples_to_features(
			train_examples, label_list, args.max_seq_length, tokenizer, output_mode)
		logger.info("***** Running training *****")
		logger.info("  Num examples = %d", len(train_examples))
		logger.info("  Batch size = %d", args.train_batch_size)
		logger.info("  Num steps = %d", num_train_optimization_steps)
		all_input_ids = torch.tensor([f.input_ids for f in train_features], dtype=torch.long)
		all_input_mask = torch.tensor([f.input_mask for f in train_features], dtype=torch.long)
		all_segment_ids = torch.tensor([f.segment_ids for f in train_features], dtype=torch.long)


		if( output_mode == "classification" or output_mode == "multi_classification"):
			all_label_ids = torch.tensor([f.label_id for f in train_features], dtype=torch.long)
		elif( output_mode == "regression"):
			all_label_ids = torch.tensor([f.label_id for f in train_features], dtype=torch.float)
		train_data = TensorDataset(all_input_ids, all_input_mask, all_segment_ids, all_label_ids)

		if args.local_rank == -1:
			train_sampler = RandomSampler(train_data)
		else:
			train_sampler = DistributedSampler(train_data)
		train_dataloader = DataLoader(train_data, sampler=train_sampler, batch_size=args.train_batch_size)

		model.train()
		for _ in trange(int(args.num_train_epochs), desc="Epoch"):
			tr_loss = 0
			nb_tr_examples, nb_tr_steps = 0, 0
			for step, batch in enumerate(tqdm(train_dataloader, desc="Iteration")):
				batch = tuple(t.to(device) for t in batch)

				input_ids, input_mask, segment_ids, label_ids = batch

				# define a new function to compute loss values for both output_modes
				logits = model(input_ids, segment_ids, input_mask)


				if(output_mode == "multi_classification"):
					loss_fct = CrossEntropyLoss()
					loss = loss_fct( logits[0].view(-1, num_labels[0]), label_ids[:,0].view(-1) )
					loss += 16*loss_fct( logits[1].view(-1, num_labels[1]), label_ids[:,1].view(-1) ) * (label_ids[:,0].float().view(-1)).mean()
					loss += 16*loss_fct( logits[2].view(-1, num_labels[2]), label_ids[:,2].view(-1) ) * (label_ids[:,1].float().view(-1)).mean()
				elif output_mode == "classification":
					loss_fct = CrossEntropyLoss()
					loss = loss_fct(logits.view(-1, num_labels), label_ids.view(-1))
				elif output_mode == "regression":
					loss_fct = MSELoss()
					loss = loss_fct(logits.view(-1), label_ids.view(-1))
				
				if n_gpu > 1:
					loss = loss.mean() # mean() to average on multi-gpu.
				if args.gradient_accumulation_steps > 1:
					loss = loss / args.gradient_accumulation_steps

				if args.fp16:
					optimizer.backward(loss)
				else:
					loss.backward()

				tr_loss += loss.item()
				nb_tr_examples += input_ids.size(0)
				nb_tr_steps += 1
				if (step + 1) % args.gradient_accumulation_steps == 0:
					if args.fp16:
						# modify learning rate with special warm up BERT uses
						# if args.fp16 is False, BertAdam is used that handles this automatically
						lr_this_step = args.learning_rate * warmup_linear(global_step/num_train_optimization_steps, args.warmup_proportion)
						for param_group in optimizer.param_groups:
							param_group['lr'] = lr_this_step
					optimizer.step()
					optimizer.zero_grad()
					global_step += 1

	if args.do_train and (args.local_rank == -1 or torch.distributed.get_rank() == 0):
		# Save a trained model, configuration and tokenizer
		model_to_save = model.module if hasattr(model, 'module') else model  # Only save the model it-self

		# If we save using the predefined names, we can load using `from_pretrained`
		output_model_file = os.path.join(args.output_dir, WEIGHTS_NAME)
		output_config_file = os.path.join(args.output_dir, CONFIG_NAME)

		torch.save(model_to_save.state_dict(), output_model_file)
		model_to_save.config.to_json_file(output_config_file)
		tokenizer.save_vocabulary(args.output_dir)

		# Load a trained model and vocabulary that you have fine-tuned
		model = BertForSequenceClassification.from_pretrained(args.output_dir, num_labels=num_labels)
		tokenizer = BertTokenizer.from_pretrained(args.output_dir, do_lower_case=args.do_lower_case)
	else:
		model = BertForSequenceClassification.from_pretrained(args.bert_model, num_labels=num_labels)
	model.to(device)

	if args.do_eval and (args.local_rank == -1 or torch.distributed.get_rank() == 0):
		eval_examples = processor.get_dev_examples(args.data_dir)
		eval_features = convert_examples_to_features(
			eval_examples, label_list, args.max_seq_length, tokenizer, output_mode)
		logger.info("***** Running evaluation *****")
		logger.info("  Num examples = %d", len(eval_examples))
		logger.info("  Batch size = %d", args.eval_batch_size)
		all_input_ids = torch.tensor([f.input_ids for f in eval_features], dtype=torch.long)
		all_input_mask = torch.tensor([f.input_mask for f in eval_features], dtype=torch.long)
		all_segment_ids = torch.tensor([f.segment_ids for f in eval_features], dtype=torch.long)

		if( output_mode == "classification" or output_mode == "multi_classification"):
			all_label_ids = torch.tensor([f.label_id for f in eval_features], dtype=torch.long)
		elif( output_mode == "regression"):
			all_label_ids = torch.tensor([f.label_id for f in eval_features], dtype=torch.float)
		eval_data = TensorDataset(all_input_ids, all_input_mask, all_segment_ids, all_label_ids)

		# Run prediction for full data
		eval_sampler = SequentialSampler(eval_data)
		eval_dataloader = DataLoader(eval_data, sampler=eval_sampler, batch_size=args.eval_batch_size)

		model.eval()
		eval_loss = 0
		nb_eval_steps = 0
		
		preds = []
		if(output_mode == "multi_classification"):
			for i in range(len(label_list)):
				preds.append([])

		for batch in tqdm(eval_dataloader, desc="Evaluating"):
			batch = tuple(t.to(device) for t in batch)

			input_ids, input_mask, segment_ids, label_ids = batch

			with torch.no_grad():
				logits = model(input_ids, segment_ids, input_mask)

			# create eval loss and other metric required by the task
			if(output_mode == "multi_classification"): 
				loss_fct = CrossEntropyLoss()
				tmp_eval_loss = loss_fct( logits[0].view(-1, num_labels[0]), label_ids[:,0].view(-1) )
				tmp_eval_loss += loss_fct( logits[1].view(-1, num_labels[1]), label_ids[:,1].view(-1) ) * (label_ids[:,0].float().view(-1)).mean()
				tmp_eval_loss += loss_fct( logits[2].view(-1, num_labels[2]), label_ids[:,2].view(-1) ) * (label_ids[:,1].float().view(-1)).mean()
			
			elif output_mode == "classification":
				loss_fct = CrossEntropyLoss()
				tmp_eval_loss = loss_fct(logits.view(-1, num_labels), label_ids.view(-1))
			elif output_mode == "regression":
				loss_fct = MSELoss()
				tmp_eval_loss = loss_fct(logits.view(-1), label_ids.view(-1))
			

			eval_loss += tmp_eval_loss.mean().item()
			nb_eval_steps += 1

			if(output_mode == "multi_classification"): 
				for i,logit in enumerate(logits):
					if(len(preds[i]) == 0):
						preds[i].append(logit.detach().cpu().numpy())
					else:
						preds[i][0] = np.append(
							preds[i][0], logit.detach().cpu().numpy(), axis=0)
			else:
				if len(preds) == 0:
					preds.append(logits.detach().cpu().numpy())
				else:
					preds[0] = np.append(
						preds[0], logits.detach().cpu().numpy(), axis=0)

		eval_loss = eval_loss / nb_eval_steps

		if(output_mode == "multi_classification"): 
			pass
		else:
			if output_mode == "classification":
				preds = np.argmax(preds, axis=1)
			elif output_mode == "regression":
				preds = np.squeeze(preds)

		result = compute_metrics(task_name, preds, all_label_ids.numpy())
		
		loss = tr_loss/nb_tr_steps if args.do_train else None

		result['eval_loss'] = eval_loss
		result['global_step'] = global_step
		result['loss'] = loss

		output_eval_file = os.path.join(args.output_dir, "eval_results.txt")
		with open(output_eval_file, "w") as writer:
			logger.info("***** Eval results *****")
			for key in sorted(result.keys()):
				logger.info("  %s = %s", key, str(result[key]))
				writer.write("%s = %s\n" % (key, str(result[key])))
	
	if args.do_test and (args.local_rank == -1 or torch.distributed.get_rank() == 0):
		eval_examples = processor.get_test_examples(args.data_dir)
		eval_features = convert_examples_to_features(eval_examples, label_list, args.max_seq_length, tokenizer, output_mode)
		logger.info("***** Running evaluation *****")
		logger.info("  Num examples = %d", len(eval_examples))
		logger.info("  Batch size = %d", args.eval_batch_size)
		all_index = torch.tensor([f.guid for f in eval_features], dtype=torch.long)
		all_input_ids = torch.tensor([f.input_ids for f in eval_features], dtype=torch.long)
		all_input_mask = torch.tensor([f.input_mask for f in eval_features], dtype=torch.long)
		all_segment_ids = torch.tensor([f.segment_ids for f in eval_features], dtype=torch.long)

		test_data = TensorDataset(all_index,all_input_ids, all_input_mask, all_segment_ids)
		# Run prediction for full data
		test_sampler = SequentialSampler(test_data)
		test_dataloader = DataLoader(test_data, sampler=test_sampler, batch_size=args.eval_batch_size)

		model.eval()
		nb_eval_steps = 0
		preds = []
		if(output_mode == "multi_classification"): 
			preds = [[],[],[]]
		total_index = []
		for index,input_ids, input_mask, segment_ids in tqdm(test_dataloader, desc="Evaluating"):
			total_index.extend(index.tolist())

			input_ids = input_ids.to(device)
			input_mask = input_mask.to(device)
			segment_ids = segment_ids.to(device)

			with torch.no_grad():
				logits = model(input_ids, segment_ids, input_mask)

			if(output_mode == "multi_classification"): 
				for i,logit in enumerate(logits):
					if(len(preds[i]) == 0):
						preds[i].append(logit.detach().cpu().numpy())
					else:
						preds[i][0] = np.append(
							preds[i][0], logit.detach().cpu().numpy(), axis=0)
			else:
				if len(preds) == 0:
					preds.append(logits.detach().cpu().numpy())
				else:
					preds[0] = np.append(
						preds[0], logits.detach().cpu().numpy(), axis=0)

		if(output_mode == "multi_classification"): 
			if(args.test_task == 'taska'):
				preds = preds[0][0]
				label_map= ['NOT','OFF']
			elif(args.test_task == 'taskb'):
				preds = preds[1][0]
				label_map= ['UNT', 'TIN']
			elif(args.test_task == 'taskc'):
				preds = preds[2][0]
				label_map= ['OTH', 'GRP', 'IND']
				
			preds = np.argmax(preds, axis=-1)
		else:
			preds = preds[0]
			if output_mode == "classification":
				preds = np.argmax(preds, axis=1)
			elif output_mode == "regression":
				preds = np.squeeze(preds)
			
			label_map = processor.get_labels()


		output_test_file = os.path.join(args.output_dir, "{0}_preds.txt".format(args.test_task))
		with open(output_test_file, "w") as writer:
			logger.info("***** test results *****")
			writer.write("Id,Category\n")
			for i in range(preds.shape[0]):
				writer.write("{0},{1}\n".format(total_index[i],label_map[preds[i]] ))


if __name__ == "__main__":
	main()
