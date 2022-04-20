from typing import Tuple, List

import torch

from kal.active_strategies.strategy import Strategy


class EntropySampling(Strategy):

    def loss(self, preds: torch.Tensor, *args, **kwargs) -> torch.Tensor:
        assert len(preds.shape) > 1, "Entropy Sampling requires multi-class prediction"

        log_probs = torch.log(preds)
        uncertainties = - (preds * log_probs).sum(1)

        return uncertainties

    def selection(self, preds: torch.Tensor, labelled_idx: list, n_p: int,
                  *args, **kwargs) -> Tuple[List, torch.Tensor]:

        e_loss = self.loss(preds)

        e_loss[torch.as_tensor(labelled_idx)] = -1

        e_idx = torch.argsort(e_loss, descending=True)
        e_idx = e_idx[:n_p].detach().cpu().numpy().tolist()

        assert torch.as_tensor([idx not in labelled_idx for idx in e_idx]).all(), \
            "Error: selected idx already labelled"

        return e_idx, e_loss


class EntropyDropoutSampling(EntropySampling):

    def loss(self, _, *args, preds_dropout: torch.Tensor = None, **kwargs) -> torch.Tensor:
        assert preds_dropout is not None, \
            "Need to pass predictions made with dropout to calculate this metric"

        return super().loss(preds_dropout, *args, **kwargs)

    def selection(self, preds: torch.Tensor, labelled_idx: list, n_p: int, *args,
                  preds_dropout=None, **kwargs) -> Tuple[List, torch.Tensor]:
        assert preds_dropout is not None, \
            "Need to pass predictions made with dropout to calculate this metric"

        e_loss = self.loss(preds, preds_dropout=preds_dropout)

        e_loss[torch.as_tensor(labelled_idx)] = -1

        e_idx = torch.argsort(e_loss, descending=True)
        e_idx = e_idx[:n_p].detach().cpu().numpy().tolist()

        assert torch.as_tensor([idx not in labelled_idx for idx in e_idx]).all(), \
            "Error: selected idx already labelled"

        return e_idx, e_loss
