from typing import Tuple, List

import numpy as np
import torch

from kal.active_strategies.strategy import Strategy


class AdversarialDeepFoolSampling(Strategy):

    def __init__(self, *args, max_iter=50, k_sample=1000,
                 **kwargs):
        self.max_iter = max_iter
        self.k_sample = k_sample
        super(AdversarialDeepFoolSampling, self).__init__(*args, **kwargs)

    def loss(self, preds: torch.Tensor, *args, clf: torch.nn.Module = None,  x: torch.Tensor = None,
             **kwargs) -> torch.Tensor:
        assert clf is not None, "Need to pass the classifier in the Adv DeepFool selection"
        assert x is not None, "Need to pass the Input data in the Adv DeepFool selection"
        assert len(preds.shape) > 1, "Adversarial Sampling requires multi-class prediction"

        dis = torch.zeros(x.shape[0])
        dev = next(clf.parameters()).device
        for j in range(x.shape[0]):
            x_j = x[j]
            nx = torch.unsqueeze(x_j, 0).to(dev)
            nx.requires_grad_()
            eta = torch.zeros(nx.shape).to(dev)

            _, out = clf(nx + eta, return_logits=True)
            n_class = out.shape[1]
            py = out.max(1)[1].item()
            ny = out.max(1)[1].item()

            i_iter = 0

            while py == ny and i_iter < self.max_iter:
                out[0, py].backward(retain_graph=True)
                grad_np = nx.grad.data.clone()
                value_l = np.inf
                ri = None

                for i in range(n_class):
                    if i == py:
                        continue

                    nx.grad.data.zero_()
                    out[0, i].backward(retain_graph=True)
                    grad_i = nx.grad.data.clone()

                    wi = grad_i - grad_np
                    fi = out[0, i] - out[0, py]
                    value_i = np.abs(fi.item()) / np.linalg.norm(wi.numpy().flatten())

                    if value_i < value_l:
                        ri = value_i / np.linalg.norm(wi.numpy().flatten()) * wi

                eta += ri.clone() if ri is not None else 0.
                nx.grad.data.zero_()
                _, out = clf(nx + eta, return_logits=True)
                py = out.max(1)[1].item()
                i_iter += 1

            eta = eta.detach()
            dis[j] = (eta * eta).sum()
        return dis

    def selection(self, preds: torch.Tensor, labelled_idx: list, n_p: int, 
                  *args, x: torch.Tensor = None, clf: torch.nn.Module = None, 
                  **kwargs) -> Tuple[List, torch.Tensor]:
        assert clf is not None, "Need to pass the classifier in the Adv DeepFool selection"
        assert x is not None, "Need to pass the Input data in the Adv DeepFool selection"
        
        n_sample = preds.shape[0]

        rand_idx = torch.randperm(n_sample)[:self.k_sample]
        rand_x = x[rand_idx]

        adv_loss = self.loss(preds, *args, clf=clf, x=rand_x, **kwargs)

        labelled_rand_idx = [i for i, idx in enumerate(rand_idx)
                             if idx in labelled_idx]
        if len(labelled_rand_idx) > 0:
            adv_loss[torch.as_tensor(labelled_rand_idx)] = 1e30

        adv_idx = torch.argsort(adv_loss)
        adv_idx = rand_idx[adv_idx]
        adv_idx = adv_idx[:n_p].detach().cpu().numpy().tolist()

        assert torch.as_tensor([idx not in labelled_idx for idx in adv_idx]).all(), \
            "Error: selected idx already labelled"
        return adv_idx, adv_loss
