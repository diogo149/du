import du
import random
import numpy as np
import torch
import torch.nn.functional as F
import torchvision.transforms as transforms
import torchvision.datasets as datasets


def adjust_learning_rate(optimizer, lr):
    """Adjust the learning rate of an optimizer"""
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr


def save_model(trial, name, model):
    with du.timer("save model (%s) for %s:%d" %
                  (name, trial.trial_name, trial.iteration_num)):
        torch.save(model.state_dict(),
                   trial.file_path("model_%s.pth" % name))


def accuracy(output, target, topk=(1,)):
    """
    Computes the accuracy over the k top predictions for the specified
    values of k
    """
    with torch.no_grad():
        maxk = max(topk)
        batch_size = target.size(0)

        _, pred = output.topk(maxk, 1, True, True)
        pred = pred.t()
        correct = pred.eq(target.view(1, -1).expand_as(pred))

        res = []
        for k in topk:
            correct_k = correct[:k].view(-1).float().sum(0, keepdim=True)
            res.append(correct_k.mul_(100.0 / batch_size))
        return res


class AverageMeter(object):
    """Computes and stores the average and current value"""
    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count

def random_seed(seed):
    """
    randomly seed relevant values
    see: https://discuss.pytorch.org/t/what-is-manual-seed/5939/16

    note: this doesn't make everything determinisitc, because
    CuDNN may not be:
    https://pytorch.org/docs/stable/notes/randomness.html
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available() :
        torch.cuda.manual_seed_all(seed)


def cross_entropy_loss(logits, probs, axis=-1, reduction="mean"):
    """
    cross-entropy loss that supports probabilities as floats

    TODO is this the same as nn.KLDivLoss()
    """
    tmp = -torch.sum(probs * F.log_softmax(logits, dim=axis), axis=axis)
    if reduction == "mean":
        return tmp.mean()
    else:
        raise ValueError


def label_smoothing(target, epsilon, num_classes=-1):
    if target.ndim == 1 and target.dtype == torch.int64:
        target = F.one_hot(target, num_classes=num_classes).float()
    num_classes = target.shape[-1]
    uniform_weight =  epsilon / (num_classes - 1)
    target_scaling = 1. - epsilon - uniform_weight
    uniform = torch.ones_like(target) * uniform_weight
    return target * target_scaling + uniform


class ConcatDataset(torch.utils.data.Dataset):
    def __init__(self, datasets):
        self.datasets = datasets

    def __len__(self):
        return sum(map(len, self.datasets))

    def __getitem__(self, idx):
        # assumes all datasets use integer indices
        # warning: no error checking
        dataset_idx = 0
        while idx >= len(self.datasets[dataset_idx]) and dataset_idx < (len(self.datasets) - 1):
            idx -= len(self.datasets[dataset_idx])
            dataset_idx += 1
        return self.datasets[dataset_idx][idx]


class AugmentedDataset(torch.utils.data.Dataset):
    def __init__(self, dataset, augmented_data):
        assert len(dataset) == len(augmented_data)
        self.dataset = dataset
        self.augmented_data

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx):
        return self.dataset[idx] + (self.augmented_data[idx],)


def cifar10_data(*, train, augmentation=None):
    """
    train: whether or not to access the train set

    augmentation:
      "standard": translation + h flipping
      None: no augmentation
    """
    transform_list = [transforms.ToTensor(),
                      transforms.Normalize([0.4914, 0.4822, 0.4465],
                                           [0.2023, 0.1994, 0.2010])]
    if augmentation is None:
        # do nothing
        pass
    elif augmentation == "standard":
        transform_list = [
            transforms.RandomCrop(32, padding=4),
            transforms.RandomHorizontalFlip(),
        ] + transform_list
    elif isinstance(augmentation, list):
        transform_list = augmentation + transform_list
    else:
        raise ValueError

    transform = transforms.Compose(transform_list)

    return datasets.CIFAR10(
        root='~/data',
        train=train,
        download=True,
        transform=transform)


def mnist_data(*, train, augmentation=None):
    assert augmentation is None
    transform = transforms.Compose([transforms.ToTensor(),
                                    transforms.Normalize((0.1307,), (0.3081,))])
    return datasets.MNIST(
        root="~/data",
        train=train,
        download=True,
        transform=transform)
