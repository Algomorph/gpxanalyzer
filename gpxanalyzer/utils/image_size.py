#-------------------------------------------------------------------------------
# Name:        get_image_info
# Purpose:     extract image dimensions & number of channels given a file path
#
# Author:      Paulo Scardine, EJEHardenberg, Gregory Kramida (based on code from Emmanuel VAISSE)
#
# Created:     26/09/2013
# Copyright:   (c) Paulo Scardine 2013
# Licence:     MIT
#-------------------------------------------------------------------------------
#!/usr/bin/env python
import os
import struct


FILE_UNKNOWN = "Sorry, don't know how to get size for this file."

class UnknownImageFormat(Exception):
    pass

def get_image_info(file_path):
    """
    Return (width, height) for a given img file content - no external
    dependencies except the os and struct builtin modules
    """
    size = os.path.getsize(file_path)

    with open(file_path, "rb") as im_file:
        height = -1
        width = -1
        data = im_file.read(26)
        msg = " raised while trying to decode as JPEG."
        n_channels = 3

        if (size >= 10) and data[:6] in ('GIF87a', 'GIF89a'):
            # GIFs
            w, h = struct.unpack("<HH", data[6:10])
            width = int(w)
            height = int(h)
            n_channels = 3
        elif ((size >= 24) and data.startswith('\211PNG\r\n\032\n')
              and (data[12:16] == 'IHDR')):
            # PNGs
            w, h, d, t = struct.unpack(">LLBB", data[16:26])
            width = int(w)
            height = int(h)
            if(t == 2 or t==3):
                n_channels = 3 #color/palette used
            elif(t == 4):
                n_channels = 2 #grey and alpha channel used
            elif(t == 6):
                n_channels = 4 #RGB and alpha channel used
            else:
                n_channels = 1 #greyscale
        elif (size >= 16) and data.startswith('\211PNG\r\n\032\n'):
            # older PNGs
            w, h, d, t = struct.unpack(">LL", data[8:18])
            width = int(w)
            height = int(h)
            if(t == 2 or t==3):
                n_channels = 3 #color/palette used
            elif(t == 4):
                n_channels = 2 #grey and alpha channel used
            elif(t == 6):
                n_channels = 4 #RGB and alpha channel used
            else:
                n_channels = 1 #greyscale
        elif (size >= 2) and data.startswith('\377\330'):
            # JPEG
            im_file.seek(0)
            im_file.read(2)
            b = im_file.read(1)
            try:
                while (b and ord(b) != 0xDA):
                    while (ord(b) != 0xFF): b = im_file.read(1)
                    while (ord(b) == 0xFF): b = im_file.read(1)
                    if (ord(b) >= 0xC0 and ord(b) <= 0xC3):
                        im_file.read(3)
                        h, w, d = struct.unpack(">HHB", im_file.read(5))
                        break
                    else:
                        im_file.read(int(struct.unpack(">H", im_file.read(2))[0])-2)
                    b = im_file.read(1)

                width = int(w)
                height = int(h)
                n_channels = int(d)
            except struct.error:
                raise UnknownImageFormat("StructError" + msg)
            except ValueError:
                raise UnknownImageFormat("ValueError" + msg)
            except Exception as e:
                raise UnknownImageFormat(e.__class__.__name__ + msg)
        elif size >= 2:
            #see http://en.wikipedia.org/wiki/ICO_(file_format)
            im_file.seek(0)
            reserved = im_file.read(2)
            if 0 != struct.unpack("<H", reserved )[0]:
                raise UnknownImageFormat(FILE_UNKNOWN)
            im_file.read(2)#format
            assert 1 == struct.unpack("<H", format)[0]
            num = im_file.read(2)
            num = struct.unpack("<H", num)[0]
            if num > 1:
                import warnings
                warnings.warn("ICO im_file contains more than one image")
            #http://msdn.microsoft.com/en-us/library/ms997538.aspx
            w = im_file.read(1)
            h = im_file.read(1)
            d = im_file.read(1)
            width = ord(w)
            height = ord(h)
            n_channels = ord(d)
        else:
            raise UnknownImageFormat(FILE_UNKNOWN)

    return width, height, n_channels
