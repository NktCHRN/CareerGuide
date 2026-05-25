"""CareerRNN — bidirectional custom GRU with attention pooling.

Reproduced VERBATIM from the training notebook `gru-attn-bidirectional-final`
(cell defining CustomGRUCell / CustomGRU / CareerRNN). Do NOT change the layer
order or signatures — the checkpoint `gru-attn-bidirectional-final_seed4.pth`
is loaded with strict=True and any structural drift breaks `load_state_dict`.

Per-step features = free-text role embedding, months, sequence-level industry.
The user's skill vector is NOT consumed by the GRU cells — it is projected and
concatenated to the pooled GRU output before the final linear projection.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class CustomGRUCell(nn.Module):
    def __init__(self, input_dim, hidden_dim, months_dim, industry_dim):
        super().__init__()
        gate_in = input_dim + months_dim + industry_dim
        self.x2h = nn.Linear(gate_in, 3 * hidden_dim)
        self.h2h = nn.Linear(hidden_dim, 3 * hidden_dim)

    def forward(self, x, m, ind, h):
        combined = torch.cat([x, m, ind], dim=-1)
        rx, zx, nx = self.x2h(combined).chunk(3, dim=-1)
        rh, zh, nh = self.h2h(h).chunk(3, dim=-1)
        r = torch.sigmoid(rx + rh)
        z = torch.sigmoid(zx + zh)
        n = torch.tanh(nx + r * nh)
        return (1 - z) * n + z * h


class CustomGRU(nn.Module):
    def __init__(self, input_dim, hidden_dim, months_dim, n_industries, industry_dim, dropout=0.0):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.n_industries = n_industries
        self.months_proj = nn.Sequential(nn.Linear(1, months_dim), nn.ReLU(), nn.Dropout(dropout))
        self.industry_emb = nn.Sequential(nn.Linear(n_industries, industry_dim), nn.ReLU(), nn.Dropout(dropout))
        self.summary_proj = nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.Tanh())
        self.fwd_cell = CustomGRUCell(input_dim, hidden_dim, months_dim, industry_dim)
        self.bwd_cell = CustomGRUCell(input_dim, hidden_dim, months_dim, industry_dim)
        self.attn = nn.Sequential(nn.Linear(2 * hidden_dim, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, 1, bias=False))

    @property
    def output_dim(self):
        return 2 * self.hidden_dim

    def _pool_industry(self, inds, months, lengths):
        B, L = inds.shape
        inds_oh = F.one_hot(inds, num_classes=self.n_industries).float()
        i_all = self.industry_emb(inds_oh)
        lengths_dev = lengths.to(inds.device)
        mask = (torch.arange(L, device=inds.device)[None, :] < lengths_dev[:, None]).float()
        weights = torch.expm1(months).clamp(min=0.0) * mask
        masked_sum = (i_all * weights.unsqueeze(-1)).sum(dim=1)
        denom = weights.sum(dim=1, keepdim=True).clamp(min=1e-6)
        return masked_sum / denom

    def forward(self, padded, months, inds, summary, lengths):
        B, L, _ = padded.shape
        m_all = self.months_proj(months.unsqueeze(-1))
        ind = self._pool_industry(inds, months, lengths)
        h0 = self.summary_proj(summary)
        lengths_dev = lengths.to(padded.device)
        valid = torch.arange(L, device=padded.device)[None, :] < lengths_dev[:, None]
        h_fwd = h0
        fwd_outputs = []
        for t in range(L):
            new_h = self.fwd_cell(padded[:, t, :], m_all[:, t, :], ind, h_fwd)
            h_fwd = torch.where(valid[:, t:t + 1], new_h, h_fwd)
            fwd_outputs.append(h_fwd)
        fwd_outputs = torch.stack(fwd_outputs, dim=1)
        h_bwd = h0
        bwd_outputs = [None] * L
        for t in range(L - 1, -1, -1):
            new_h = self.bwd_cell(padded[:, t, :], m_all[:, t, :], ind, h_bwd)
            h_bwd = torch.where(valid[:, t:t + 1], new_h, h_bwd)
            bwd_outputs[t] = h_bwd
        bwd_outputs = torch.stack(bwd_outputs, dim=1)
        outputs = torch.cat([fwd_outputs, bwd_outputs], dim=-1)
        scores = self.attn(outputs).squeeze(-1)
        scores = scores.masked_fill(~valid, float("-inf"))
        w = scores.softmax(dim=-1)
        return (outputs * w.unsqueeze(-1)).sum(dim=1)


class CareerRNN(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, dropout=0.0, months_dim=16,
                 n_industries=2, industry_dim=32, skill_input_dim=None, skill_dim=64):
        super().__init__()
        if skill_input_dim is None:
            skill_input_dim = 2 * input_dim
        self.gru = CustomGRU(input_dim, hidden_dim, months_dim, n_industries, industry_dim, dropout)
        self.skills_proj = nn.Sequential(nn.Linear(skill_input_dim, skill_dim), nn.ReLU(), nn.Dropout(dropout))
        self.drop = nn.Dropout(dropout)
        self.proj = nn.Linear(self.gru.output_dim + skill_dim, output_dim)

    def forward(self, padded, months, inds, skills, summary, lengths):
        pooled = self.gru(padded, months, inds, summary, lengths)
        s = self.skills_proj(skills)
        return self.proj(self.drop(torch.cat([pooled, s], dim=-1)))
