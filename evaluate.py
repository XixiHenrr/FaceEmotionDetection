import argparse
import warnings

import torch
import torch.nn as nn
from sklearn.metrics import precision_score, f1_score, recall_score, confusion_matrix
import matplotlib.pyplot as plt
import numpy as np

from dataset import get_dataloaders
from utils import get_model

warnings.filterwarnings("ignore")

parser = argparse.ArgumentParser(description='')
parser.add_argument('--batch_size', default=128, type=int)
parser.add_argument('--seed', default=0, type=int)
parser.add_argument('--data_path', default='./fer2013.csv', type=str)
parser.add_argument('--checkpoint', default='./best_checkpoint.tar', type=str)
parser.add_argument('--arch', default="ResNet18", type=str)
parser.add_argument('--Ncrop', default=True, type=eval)


def correct_count(output, target, topk=(1,)):
    """Computes the top k corrrect count for the specified values of k"""
    maxk = max(topk)

    _, pred = output.topk(maxk, 1, True, True)
    pred = pred.t()
    correct = pred.eq(target.view(1, -1).expand_as(pred))

    res = []
    for k in topk:
        correct_k = correct[:k].contiguous().view(-1).float().sum(0, keepdim=True)
        res.append(correct_k)
    return res


def draw_confusion_matrix(label_true, label_pred, label_name, title="Confusion Matrix", pdf_save_path=None, dpi=100):

    """"example：
            draw_confusion_matrix(label_true=y_gt,
                          label_pred=y_pred,
                          label_name=["Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral"],
                          title="Confusion Matrix",
                          pdf_save_path="Confusion_Matrix.png",
                          dpi=300)

    """
    cm = confusion_matrix(y_true=label_true, y_pred=label_pred, normalize='true')

    plt.imshow(cm, cmap='Blues')
    plt.title(title)
    plt.xlabel("Predict label")
    plt.ylabel("Truth label")
    plt.yticks(range(label_name.__len__()), label_name)
    plt.xticks(range(label_name.__len__()), label_name, rotation=45)

    plt.tight_layout()

    plt.colorbar()

    for i in range(label_name.__len__()):
        for j in range(label_name.__len__()):
            color = (1, 1, 1) if i == j else (0, 0, 0)  # 对角线字体白色，其他黑色
            value = float(format('%.2f' % cm[j, i]))
            plt.text(i, j, value, verticalalignment='center', horizontalalignment='center', color=color)

    # plt.show()
    if not pdf_save_path is None:
        plt.savefig(pdf_save_path, bbox_inches='tight', dpi=dpi)


def evaluate(net, dataloader, loss_fn, Ncrop, device):
    net = net.eval()
    loss_tr, n_samples = 0.0, 0.0

    y_pred = []
    y_gt = []

    correct_count1 = 0
    correct_count2 = 0

    for data in dataloader:
        inputs, labels = data
        inputs, labels = inputs.to(device), labels.to(device)

        if Ncrop:
            # fuse crops and batchsize
            bs, ncrops, c, h, w = inputs.shape
            inputs = inputs.view(-1, c, h, w)

            # forward
            outputs = net(inputs)

            # combine results across the crops
            outputs = outputs.view(bs, ncrops, -1)
            outputs = torch.sum(outputs, dim=1) / ncrops
        else:
            outputs = net(inputs)

        loss = loss_fn(outputs, labels)

        # calculate performance metrics
        loss_tr += loss.item()

        # accuracy
        counts = correct_count(outputs, labels, topk=(1, 2))
        correct_count1 += counts[0].item()
        correct_count2 += counts[1].item()

        _, preds = torch.max(outputs.data, 1)
        n_samples += labels.size(0)

        y_pred.extend(pred.item() for pred in preds)
        y_gt.extend(y.item() for y in labels)

    acc1 = 100 * correct_count1 / n_samples
    acc2 = 100 * correct_count2 / n_samples
    loss = loss_tr / n_samples
    print("--------------------------------------------------------")
    print("Top 1 Accuracy: %2.6f %%" % acc1)
    print("Top 2 Accuracy: %2.6f %%" % acc2)
    print("Loss: %2.6f" % loss)
    print("Precision: %2.6f" % precision_score(y_gt, y_pred, average='micro'))
    print("Recall: %2.6f" % recall_score(y_gt, y_pred, average='micro'))
    print("F1 Score: %2.6f" % f1_score(y_gt, y_pred, average='micro'))
    print("Confusion Matrix:\n", confusion_matrix(y_gt, y_pred), '\n')

    return y_gt, y_pred

def main():
    args = parser.parse_args()

    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

    loss_fn = nn.CrossEntropyLoss()

    model = get_model(args.arch).to(device)
    print(model)
    checkpoint = torch.load(args.checkpoint)
    model.load_state_dict(checkpoint['model_state_dict'])

    train_loader, val_loader, test_loader = get_dataloaders(augment=False)
    with torch.no_grad():
        print("Train")
        train_eval = evaluate(model, train_loader, loss_fn, args.Ncrop, device)
        y_gt, y_pred = train_eval
        draw_confusion_matrix(label_true=y_gt,
                              label_pred=y_pred,
                              label_name=["Angry", "Happy", "Sad", "Neutral"],
                              title="Confusion Matrix on Training Set",
                              pdf_save_path="Confusion Matrix on Training Set.png",
                              dpi=300)

        plt.clf()

        print("Val")
        val_eval = evaluate(model, val_loader, loss_fn, args.Ncrop, device)
        y_gt, y_pred = val_eval
        draw_confusion_matrix(label_true=y_gt,
                              label_pred=y_pred,
                              label_name=["Angry", "Happy", "Sad", "Neutral"],
                              title="Confusion Matrix on Val Set",
                              pdf_save_path="Confusion Matrix on Val Set.png",
                              dpi=300)

        plt.clf()

        print("Test")
        test_eval = evaluate(model, test_loader, loss_fn, args.Ncrop, device)
        y_gt, y_pred = test_eval
        draw_confusion_matrix(label_true=y_gt,
                              label_pred=y_pred,
                              label_name=["Angry", "Happy", "Sad", "Neutral"],
                              title="Confusion Matrix on Test Set",
                              pdf_save_path="Confusion Matrix on Test Set.png",
                              dpi=300)


if __name__ == "__main__":
    main()
