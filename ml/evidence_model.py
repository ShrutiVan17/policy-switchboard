"""Semantic encoder plus explicit business evidence and a customer verdict head."""
import torch
from torch import nn


class EvidenceModel(nn.Module):
    def __init__(self,encoder,hidden_size):
        super().__init__()
        self.encoder=encoder
        self.head=nn.Sequential(nn.Linear(hidden_size+6,128),nn.GELU(),nn.Dropout(.1),nn.Linear(128,4))

    def forward(self,input_ids,attention_mask,evidence):
        hidden=self.encoder(input_ids=input_ids,attention_mask=attention_mask).last_hidden_state
        mask=attention_mask.unsqueeze(-1).to(hidden.dtype)
        pooled=(hidden*mask).sum(1)/mask.sum(1).clamp_min(1)
        pooled=torch.nn.functional.normalize(pooled,dim=-1)
        return self.head(torch.cat([pooled,evidence.to(pooled.dtype)],dim=-1))
