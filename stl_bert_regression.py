# -*- coding: utf-8 -*-
"""STL_Bert_Trial1.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1l_RmCROXIy7MZsjMxHGeEU50l3xL_bj9
"""


"""## Setup

We'll need [the Transformers library](https://huggingface.co/transformers/) by Hugging Face:
"""

# Commented out IPython magic to ensure Python compatibility.
# %reload_ext watermark
# %watermark -v -p numpy,pandas,torch,transformers

# Commented out IPython magic to ensure Python compatibility.
# Setup & Config
import transformers
from transformers import BertModel, BertTokenizer, AdamW, get_linear_schedule_with_warmup
import torch

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, classification_report
from collections import defaultdict
from sklearn.metrics import r2_score
from scipy.stats import kendalltau
from scipy.stats import spearmanr
from scipy.stats import pearsonr

from torch import nn, optim
from torch.utils.data import Dataset, DataLoader
import torch.nn.functional as F

import pytorch_lightning as pl
from pytorch_lightning.core.lightning import LightningModule
from pytorch_lightning.callbacks import ModelCheckpoint, EarlyStopping


RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
torch.manual_seed(RANDOM_SEED)
PRE_TRAINED_MODEL_NAME = 'bert-base-cased'
MAX_LEN = 200
MAX_EPOCHS = 5
NUM_CLASSES = 1
FILENAME = 'scores_wqs.csv'
BATCH_SIZE = 8

class AbuseDataset(Dataset):

    def __init__(self, reviews, targets, tokenizer, max_len):
      self.reviews = reviews
      self.targets = targets
      self.tokenizer = tokenizer
      self.max_len = max_len
    
    def __len__(self):
      return len(self.reviews)
    
    def __getitem__(self, item):
      review = str(self.reviews[item])
      target = self.targets[item]

      encoding = self.tokenizer.encode_plus(
        review,
        add_special_tokens=True,
        truncation = True,
        max_length=self.max_len,
        return_token_type_ids=False,
        pad_to_max_length=True,
        return_attention_mask=True,
        return_tensors='pt',
      )

      return {
        'review_text': review,
        'input_ids': encoding['input_ids'].flatten(),
        'attention_mask': encoding['attention_mask'].flatten(),
        'targets': torch.tensor(target, dtype=torch.float)
      }

class Abuse_lightning(LightningModule):

  def __init__(self, filename, n_classes, MAX_LEN, PRE_TRAINED_MODEL_NAME, RANDOM_SEED, batch_size, max_epochs):
    
    super(Abuse_lightning, self).__init__()
    self.save_hyperparameters()
    self.RANDOM_SEED = RANDOM_SEED
    self.n_classes = n_classes
    self.filename = filename
    self.max_len = MAX_LEN
    self.batch_size = batch_size
    self.max_epochs = max_epochs

    self.PRE_TRAINED_MODEL_NAME = PRE_TRAINED_MODEL_NAME
    self.bert = BertModel.from_pretrained(PRE_TRAINED_MODEL_NAME)
    self.drop = nn.Dropout(p=0.0)
    self.out = nn.Linear(self.bert.config.hidden_size, n_classes)
    self.loss = nn.MSELoss()

  ################################ DATA PREPARATION ############################################
    
  def prepare_data(self):
    # download only (not called on every GPU, just the root GPU per node)
    df = pd.read_csv(self.filename)
    self.df_train, self.df_test = train_test_split(df, test_size=0.2, random_state=self.RANDOM_SEED)
    self.df_val, self.df_test = train_test_split(self.df_test, test_size=0.5, random_state=self.RANDOM_SEED)
    # print('Shape of data: ',self.df_train.shape, self.df_val.shape, self.df_test.shape)
    self.tokenizer = BertTokenizer.from_pretrained(self.PRE_TRAINED_MODEL_NAME)

  # @pl.data_loader
  def train_dataloader(self):
    
    ds = AbuseDataset(reviews=self.df_train.comment.to_numpy(), targets=self.df_train.Score.to_numpy(),
                          tokenizer=self.tokenizer,max_len=self.max_len)
    
    return DataLoader(ds, batch_size=self.batch_size,num_workers=4)
    
  # @pl.data_loader
  def val_dataloader(self):
    
    ds = AbuseDataset(reviews=self.df_val.comment.to_numpy(), targets=self.df_val.Score.to_numpy(),
                          tokenizer=self.tokenizer,max_len=self.max_len)
    
    return DataLoader(ds, batch_size=self.batch_size,num_workers=4)
  
  # @pl.data_loader
  def test_dataloader(self):
    
    ds = AbuseDataset(reviews=self.df_test.comment.to_numpy(), targets=self.df_test.Score.to_numpy(),
                          tokenizer=self.tokenizer,max_len=self.max_len)
    
    return DataLoader(ds, batch_size=self.batch_size,num_workers=4)

  
  ################################ MODEL AND TRAINING PREPARATION ############################################  
  
  def forward(self, input_ids, attention_mask):
    _, pooled_output = self.bert(
      input_ids=input_ids,
      attention_mask=attention_mask
    )
    output = self.drop(pooled_output)
    return self.out(output)
  
  def training_step(self, d, batch_idx):

    input_ids = d["input_ids"]
    attention_mask = d["attention_mask"]
    targets = d["targets"]

    outputs = self.forward(input_ids=input_ids, attention_mask=attention_mask)
    preds = torch.tanh(outputs)
    loss = self.loss(preds.squeeze(dim = 1), targets)
    p = preds.squeeze(dim=1).to('cpu').detach().numpy()
    t = targets.to('cpu').detach().numpy()
    loss = loss.type(torch.FloatTensor)
    
    return {'prediction': p, 'target': t, 'loss': loss}

  def validation_step(self, d, batch_idx):

    input_ids = d["input_ids"]
    attention_mask = d["attention_mask"]
    targets = d["targets"]

    outputs = model(input_ids=input_ids, attention_mask=attention_mask    )
    preds = torch.tanh(outputs)
    loss = self.loss(preds.squeeze(dim = 1), targets)
    p = preds.squeeze(dim=1).to('cpu').detach().numpy()
    t = targets.to('cpu').detach().numpy()
    loss = loss.type(torch.FloatTensor)
    return {'prediction': p, 'target': t, 'loss': loss}

  def test_step(self, d, batch_idx):

    input_ids = d["input_ids"]
    attention_mask = d["attention_mask"]
    targets = d["targets"]

    outputs = model(input_ids=input_ids, attention_mask=attention_mask    )
    preds = torch.tanh(outputs)
    loss = self.loss(preds.squeeze(dim = 1), targets)
    p = preds.squeeze(dim=1).to('cpu').detach().numpy()
    t = targets.to('cpu').detach().numpy()
    loss = loss.type(torch.FloatTensor)
    return {'prediction': p, 'target': t, 'loss': loss}

  def configure_optimizers(self):

    optimizer = AdamW(self.parameters(), lr=2e-5, correct_bias=False)
    total_steps = len(self.train_dataloader()) * self.max_epochs
    scheduler = get_linear_schedule_with_warmup(optimizer,num_warmup_steps=0, num_training_steps = total_steps )
    return [optimizer], [scheduler]

  def training_epoch_end(self, outputs):

    # called at the end of the training epoch
    # outputs is an array with what you returned in validation_step for each batch
    # outputs = [{'loss': batch_0_loss}, {'loss': batch_1_loss}, ..., {'loss': batch_n_loss}] 
    avg_loss = torch.stack([x['loss'] for x in outputs]).mean()
    p = []
    for x in outputs:
      p.extend(x['prediction'])
    t = []
    for x in outputs:
      t.extend(x['target'])
    pear = pearsonr(t,p)
    spear = spearmanr(t,p)
    tau = kendalltau(t,p)
    tensor_pear = torch.tensor(pear[0])
    logs = {'train_loss': avg_loss.item(), 'pearson':pear[0], 'spearman':spear[0], 'kendall':tau[0]}
    return {'pearson':tensor_pear, 'spearman':spear[0], 'kendall':tau[0], 'loss': avg_loss, 'log': logs}

  def validation_epoch_end(self, outputs):
    # called at the end of the validation epoch
    # outputs is an array with what you returned in validation_step for each batch
    # outputs = [{'loss': batch_0_loss}, {'loss': batch_1_loss}, ..., {'loss': batch_n_loss}] 
    avg_loss = torch.stack([x['loss'] for x in outputs]).mean()
    # p = [x['prediction'] for x in outputs]
    p = []
    for x in outputs:
      p.extend(x['prediction'])
    t = []
    for x in outputs:
      t.extend(x['target'])
    pear = pearsonr(t,p)
    spear = spearmanr(t,p)
    tau = kendalltau(t,p)
    tensor_pear = torch.tensor(pear[0])
    logs = {'val_loss': avg_loss.item(), 'pearson':pear[0], 'spearman':spear[0], 'kendall':tau[0]}
    return {'pearson':tensor_pear, 'spearman':spear[0], 'kendall':tau[0], 'loss': avg_loss, 'log': logs}

  def test_epoch_end(self, outputs):
    # called at the end of the validation epoch
    # outputs is an array with what you returned in validation_step for each batch
    # outputs = [{'loss': batch_0_loss}, {'loss': batch_1_loss}, ..., {'loss': batch_n_loss}] 
    avg_loss = torch.stack([x['loss'] for x in outputs]).mean()
    p = []
    for x in outputs:
      p.extend(x['prediction'])
    t = []
    for x in outputs:
      t.extend(x['target'])
    pear = pearsonr(t,p)
    spear = spearmanr(t,p)
    tau = kendalltau(t,p)
    return {'pearson':pear[0], 'spearman':spear[0], 'kendall':tau[0], 'loss': avg_loss}

if __name__ == "__main__":

  model = Abuse_lightning(FILENAME, NUM_CLASSES , MAX_LEN, PRE_TRAINED_MODEL_NAME, RANDOM_SEED, BATCH_SIZE, MAX_EPOCHS)
  checkpoint_callback = ModelCheckpoint(
    save_top_k=1,
    verbose=True,
    monitor='pearson',
    mode='max')
  trainer = pl.Trainer(gpus = 1, max_epochs= MAX_EPOCHS, checkpoint_callback=checkpoint_callback, gradient_clip_val=1.0)
  trainer.fit(model)
  trainer.test()

# Commented out IPython magic to ensure Python compatibility.
# %load_ext tensorboard
# %tensorboard --logdir lightning_logs/