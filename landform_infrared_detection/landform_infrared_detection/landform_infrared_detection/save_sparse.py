from __future__ import division

from models_sparse import *
from utils.utils import *
from utils.datasets import *
from utils.parse_config import *

from PIL import Image

import os
import sys
import time
import datetime
import argparse
import tqdm

import torch
from torch.utils.data import DataLoader
from torchvision import datasets
from torchvision import transforms
from torch.autograd import Variable
import torch.optim as optim
import scipy.io as io
import cv2
def detect_contour(img_path,shape):
    contour_maps = np.zeros((shape[0], 1, shape[2], shape[3]))
    #print(contour_maps.shape)
    count = 0
    for path in img_path:
        img = Image.open(path)
        #img = img.transpose(Image.ROTATE_180)
        #img = img.transpose(Image.FLIP_LEFT_RIGHT)
        img = img.resize((shape[2], shape[3]), Image.BILINEAR)
        img = np.array(img)
        if (len(img.shape) == 3):
            img=img[...,0]
        xx = np.arange(0, img.shape[1], 1)
        yy = np.arange(0, img.shape[0], 1)
        pos_x, pos_y = np.meshgrid(xx, yy)
        cntr = plt.contour(pos_x, pos_y, img, 14)
        img_c = np.zeros(img.shape)
        coordinates = cntr.allsegs
        for i in range(len(cntr.layers)):
            coor_i = coordinates[i]
            for j in range(len(coor_i)):
            # print('shape of segment {} = {}'.format(j, coor_i[j].shape))
                pos = np.array(coor_i[j], dtype=np.int)
                img_c[pos[:, 1], pos[:, 0]] = cntr.layers[i]
        if np.max(img_c):
            img_c = img_c / np.max(img_c)
        else:
            img_c = img_c
        contour_maps[count, 0, :, :] = img_c

        count = count + 1
    contour_maps = torch.from_numpy(contour_maps)
                #print(img_c.shape)
    return contour_maps


def evaluate(model, path, iou_thres, conf_thres, nms_thres, img_size, batch_size):
    #print(path)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.eval()
    # Get dataloader
    dataset = ListDataset(path,img_size=img_size, augment=False, multiscale=False)
    dataloader = torch.utils.data.DataLoader(
        dataset, batch_size=batch_size, shuffle=False, num_workers=1, collate_fn=dataset.collate_fn
    )

    Tensor = torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor

    labels = []
    sample_metrics = []  # List of tuples (TP, confs, pred)
    i = 1
    for batch_i, (img_path, imgs, targets) in enumerate(
            tqdm.tqdm(dataloader, desc="Detecting objects")):  # ???????????????targets
        # sys.stderr.write(str(img_path))
        # Extract labels
        labels += targets[:, 1].tolist()
        # Rescale target
        targets[:, 2:] = xywh2xyxy(targets[:, 2:])
        targets[:, 2:] *= img_size

      
        img_maps = detect_contour(img_path, imgs.shape)
        img_maps = Variable(img_maps.to(device), requires_grad=False)
        imgs = Variable(imgs.type(Tensor), requires_grad=False)

        with torch.no_grad():
            #print("orgnial outputs")
            outputs = model(imgs, img_maps)
            outputs = np.array(outputs)
            io.savemat('plt/outputs_sparse/%d.mat'%i,{'outputs':outputs})
            i = i + 1          


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch_size", type=int, default=8, help="size of each image batch")
    parser.add_argument("--model_def", type=str, default="config/yolov3-F.cfg", help="path to model definition file")
    parser.add_argument("--data_config", type=str, default="config/F.data", help="path to data config file")
    parser.add_argument("--weights_path", type=str, default="weights/weights_sparse.pth", help="path to weights file")
    parser.add_argument("--class_path", type=str, default="data/classes.names", help="path to class label file")
    parser.add_argument("--iou_thres", type=float, default=0.5, help="iou threshold required to qualify as detected")
    parser.add_argument("--conf_thres", type=float, default=0.001, help="object confidence threshold")
    parser.add_argument("--nms_thres", type=float, default=0.5, help="iou thresshold for non-maximum suppression")
    parser.add_argument("--n_cpu", type=int, default=8, help="number of cpu threads to use during batch generation")
    parser.add_argument("--img_size", type=int, default=416, help="size of each image dimension")
    opt = parser.parse_args()
    print(opt)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    data_config = parse_data_config(opt.data_config)
    valid_path = data_config["valid"]
    class_names = load_classes(data_config["names"])

    model = Darknet(opt.model_def).to(device)
    if opt.weights_path.endswith(".weights"):
        # Load darknet weights
        model.load_darknet_weights(opt.weights_path)
    else:
        # Load checkpoint weights
        model.load_state_dict(torch.load(opt.weights_path, map_location='cpu'))

    print("Compute mAP, precision, recall...")

    evaluate(
        model,
        path=valid_path,
        iou_thres=opt.iou_thres,
        conf_thres=opt.conf_thres,
        nms_thres=opt.nms_thres,
        img_size=opt.img_size,
        batch_size=8,
    )

