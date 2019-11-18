import math

import torch
import torch.nn.functional as F
from torch import nn
from torch.nn import Parameter
from torchscope import scope
from torchvision import models

from config import device, num_classes, emb_size


class MobileFaceNet(nn.Module):
    def __init__(self):
        super(MobileFaceNet, self).__init__()
        mobilenet = models.mobilenet_v2(pretrained=True)
        # Remove linear layer
        modules = list(mobilenet.children())[:-1]
        self.model = nn.Sequential(*modules)
        self.bn1 = nn.BatchNorm2d(1280)
        self.dropout = nn.Dropout()
        self.conv1 = nn.Conv2d(1280, 512, kernel_size=1)
        self.bn2 = nn.BatchNorm2d(512)
        self.conv2 = nn.Conv2d(512, 512, kernel_size=4, stride=1, groups=512)
        self.bn3 = nn.BatchNorm1d(512)

    def forward(self, input):
        x = self.model(input)
        x = self.bn1(x)
        x = self.dropout(x)
        x = self.conv1(x)
        x = self.bn2(x)
        x = self.conv2(x)
        x = x.view(x.size(0), -1)
        x = self.bn3(x)
        return x

    def predict(self, input):
        s = self.model(input)
        return self.output(s)


class ArcMarginModel(nn.Module):
    def __init__(self, args):
        super(ArcMarginModel, self).__init__()

        self.weight = Parameter(torch.FloatTensor(num_classes, emb_size))
        nn.init.xavier_uniform_(self.weight)

        self.easy_margin = args.easy_margin
        self.m = args.margin_m
        self.s = args.margin_s

        self.cos_m = math.cos(self.m)
        self.sin_m = math.sin(self.m)
        self.th = math.cos(math.pi - self.m)
        self.mm = math.sin(math.pi - self.m) * self.m

    def forward(self, input, label):
        x = F.normalize(input)
        W = F.normalize(self.weight)
        cosine = F.linear(x, W)
        sine = torch.sqrt(1.0 - torch.pow(cosine, 2))
        phi = cosine * self.cos_m - sine * self.sin_m  # cos(theta + m)
        if self.easy_margin:
            phi = torch.where(cosine > 0, phi, cosine)
        else:
            phi = torch.where(cosine > self.th, phi, cosine - self.mm)
        one_hot = torch.zeros(cosine.size(), device=device)
        one_hot.scatter_(1, label.view(-1, 1).long(), 1)
        output = (one_hot * phi) + ((1.0 - one_hot) * cosine)
        output *= self.s
        return output


if __name__ == "__main__":
    model = MobileFaceNet()
    print(model)
    scope(model, input_size=(3, 112, 112))

#
# def _make_divisible(v, divisor, min_value=None):
#     """
#     This function is taken from the original tf repo.
#     It ensures that all layers have a channel number that is divisible by 8
#     It can be seen here:
#     https://github.com/tensorflow/models/blob/master/research/slim/nets/mobilenet/mobilenet.py
#     :param v:
#     :param divisor:
#     :param min_value:
#     :return:
#     """
#     if min_value is None:
#         min_value = divisor
#     new_v = max(min_value, int(v + divisor / 2) // divisor * divisor)
#     # Make sure that round down does not go down by more than 10%.
#     if new_v < 0.9 * v:
#         new_v += divisor
#     return new_v
#
#
# class ConvBNReLU(nn.Sequential):
#     def __init__(self, in_planes, out_planes, kernel_size=3, stride=1, groups=1):
#         padding = (kernel_size - 1) // 2
#         super(ConvBNReLU, self).__init__(
#             nn.Conv2d(in_planes, out_planes, kernel_size, stride, padding, groups=groups, bias=False),
#             nn.BatchNorm2d(out_planes, momentum=0.1),
#             nn.ReLU()
#         )
#
#
# class InvertedResidual(nn.Module):
#     def __init__(self, inp, oup, stride, expand_ratio):
#         super(InvertedResidual, self).__init__()
#         self.stride = stride
#         assert stride in [1, 2]
#
#         hidden_dim = int(round(inp * expand_ratio))
#         self.use_res_connect = self.stride == 1 and inp == oup
#
#         layers = []
#         if expand_ratio != 1:
#             # pw
#             layers.append(ConvBNReLU(inp, hidden_dim, kernel_size=1))
#         layers.extend([
#             # dw
#             ConvBNReLU(hidden_dim, hidden_dim, stride=stride, groups=hidden_dim),
#             # pw-linear
#             nn.Conv2d(hidden_dim, oup, 1, 1, 0, bias=False),
#             nn.BatchNorm2d(oup, momentum=0.1),
#         ])
#         self.conv = nn.Sequential(*layers)
#         # Replace torch.add with floatfunctional
#         self.skip_add = nn.quantized.FloatFunctional()
#
#     def forward(self, x):
#         if self.use_res_connect:
#             return self.skip_add.add(x, self.conv(x))
#         else:
#             return self.conv(x)
#
#
# class DepthwiseSeparableConv(nn.Module):
#     def __init__(self, nin, nout, kernel_size, padding, bias=False):
#         super(DepthwiseSeparableConv, self).__init__()
#         self.depthwise = nn.Conv2d(nin, nin, kernel_size=kernel_size, padding=padding, groups=nin, bias=bias)
#         self.pointwise = nn.Conv2d(nin, nout, kernel_size=1, bias=bias)
#
#     def forward(self, x):
#         out = self.depthwise(x)
#         out = self.pointwise(out)
#         return out
#
#
# class MobileFaceNet(nn.Module):
#     def __init__(self, width_mult=1.0, inverted_residual_setting=None, round_nearest=8):
#         """
#         MobileNet V2 main class
#
#         Args:
#             num_classes (int): Number of classes
#             width_mult (float): Width multiplier - adjusts number of channels in each layer by this amount
#             inverted_residual_setting: Network structure
#             round_nearest (int): Round the number of channels in each layer to be a multiple of this number
#             Set to 1 to turn off rounding
#         """
#         super(MobileFaceNet, self).__init__()
#         block = InvertedResidual
#         input_channel = 64
#         last_channel = 512
#
#         if inverted_residual_setting is None:
#             inverted_residual_setting = [
#                 # t, c, n, s
#                 [1, 64, 1, 2],
#                 [1, 64, 1, 1],
#                 [2, 64, 5, 2],
#                 [4, 128, 1, 2],
#                 [2, 128, 6, 1],
#                 [4, 128, 1, 2],
#                 [2, 128, 2, 1],
#             ]
#
#         # only check the first element, assuming user knows t,c,n,s are required
#         if len(inverted_residual_setting) == 0 or len(inverted_residual_setting[0]) != 4:
#             raise ValueError("inverted_residual_setting should be non-empty "
#                              "or a 4-element list, got {}".format(inverted_residual_setting))
#
#         # building first layer
#         input_channel = _make_divisible(input_channel * width_mult, round_nearest)
#         self.last_channel = _make_divisible(last_channel * max(1.0, width_mult), round_nearest)
#         features = [ConvBNReLU(3, input_channel, stride=1)]
#         features.append(DepthwiseSeparableConv(nin=64, nout=64, kernel_size=3, padding=0))
#         # building inverted residual blocks
#         for t, c, n, s in inverted_residual_setting:
#             output_channel = _make_divisible(c * width_mult, round_nearest)
#             for i in range(n):
#                 stride = s if i == 0 else 1
#                 features.append(block(input_channel, output_channel, stride, expand_ratio=t))
#                 input_channel = output_channel
#         # building last several layers
#         features.append(ConvBNReLU(input_channel, self.last_channel, kernel_size=1))
#         features.append(DepthwiseSeparableConv(nin=512, nout=512, kernel_size=7, padding=0))
#         features.append(nn.Conv2d(512, 128, kernel_size=1))
#         features.append(nn.BatchNorm2d(128))
#         # make it nn.Sequential
#         self.features = nn.Sequential(*features)
#         self.quant = QuantStub()
#         self.dequant = DeQuantStub()
#
#         # weight initialization
#         for m in self.modules():
#             if isinstance(m, nn.Conv2d):
#                 nn.init.kaiming_normal_(m.weight, mode='fan_out')
#                 if m.bias is not None:
#                     nn.init.zeros_(m.bias)
#             elif isinstance(m, nn.BatchNorm2d):
#                 nn.init.ones_(m.weight)
#                 nn.init.zeros_(m.bias)
#             elif isinstance(m, nn.Linear):
#                 nn.init.normal_(m.weight, 0, 0.01)
#                 nn.init.zeros_(m.bias)
#
#     def forward(self, x):
#
#         x = self.quant(x)
#
#         x = self.features(x)
#         x = x.mean([2, 3])
#         x = self.dequant(x)
#         return x
#
#     # Fuse Conv+BN and Conv+BN+Relu modules prior to quantization
#     # This operation does not change the numerics
#     def fuse_model(self):
#         for m in self.modules():
#             if type(m) == ConvBNReLU:
#                 torch.quantization.fuse_modules(m, ['0', '1', '2'], inplace=True)
#             if type(m) == InvertedResidual:
#                 for idx in range(len(m.conv)):
#                     if type(m.conv[idx]) == nn.Conv2d:
#                         torch.quantization.fuse_modules(m.conv, [str(idx), str(idx + 1)], inplace=True)
