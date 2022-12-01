import os
import random
import string

from PIL import Image, ImageDraw, ImageFont

from utils.tempfiles import reserve_tempfile

# the y coordinate for where the text and the face split
y_coord_split = 22

master_x_dict = {
    "w": [[7, 29]],
    "h": [[29, 43], [83, 98]],
    "e": [[43, 56], [98, 111], [192, 205]],
    "n": [[56, 69]],
    " ": [[69, 75], [111, 116], [213, 220], [238, 244]],
    "t": [[75, 83], [183, 192]],
    "i": [[116, 122], [220, 225]],
    "m": [[122, 143]],
    "p": [[143, 157]],
    "o": [[157, 171]],
    "s": [[171, 183], [225, 238], [244, 257], [270, 283]],
    "r": [[205, 213]],
    "u": [[257, 270]],
    "!": [[282, 289]],
    "😳": [[289, 312]],
}

# [should flip over x axis, should flip over y axis], [x1, x2]
bootleg_x_dict = {
    "a": [[True, False], [146, 155]],
    "q": [[True, False], [143, 155]],
    "b": [[False, True], [143, 157]],
    "d": [[True, True], [143, 157]],
    "c": [[False, False], [157, 167]],
}

# list of all avalable charecters
master_char_list = list(master_x_dict.keys()) + list(bootleg_x_dict.keys())


def get_text_dimensions(text_string, font):
    # https://stackoverflow.com/a/46220683/9263761
    ascent, descent = font.getmetrics()

    text_width = font.getmask(text_string).getbbox()[2]
    text_height = font.getmask(text_string).getbbox()[3] + descent

    return text_width, text_height


# get input string
def sus(input_string: str):
    """
    Cuts and slices the popular Jerma sus meme to any message
    :param input_string: text to make the message with
    :return: filename of generated image
    """
    master_im = Image.open("rendering/images/imposter.jpg")

    input_string = input_string.lower().replace(":flushed:", "😳")

    font = ImageFont.truetype("rendering/fonts/arial.ttf", 13)

    final_image = Image.new('RGB', (len(input_string) * 23, master_im.height))

    # keeps track of the total width of the image, the width of each strip is added at the end of each loop
    total_width = 0
    # used for predictable letter selection
    stringsofar = ""
    # any cheatmode letter will be selected ONCE
    cheatletters = {}

    for char in input_string:
        if char in master_x_dict.keys():
            # this code changes the random selection of duplicate letters to a looping pattern
            # this fixes the issue where putting in the original message won't return the original image.
            chars = master_x_dict[char]
            ind = stringsofar.count(char) % len(chars)
            x_coords = chars[ind]

            letter = master_im.crop((x_coords[0], 0, x_coords[1], y_coord_split))
            face = master_im.crop((x_coords[0], y_coord_split, x_coords[1], master_im.height))

        elif char in bootleg_x_dict.keys():
            x_coords = bootleg_x_dict[char][1]

            letter = master_im.crop((x_coords[0], 0, x_coords[1], y_coord_split))
            face = master_im.crop((x_coords[0], y_coord_split, x_coords[1], master_im.height))

            # flip over x?
            if bootleg_x_dict[char][0][0]:
                letter = letter.transpose(Image.FLIP_LEFT_RIGHT)
                face = face.transpose(Image.FLIP_LEFT_RIGHT)

            # flip over y?
            if bootleg_x_dict[char][0][1]:
                letter = letter.transpose(Image.FLIP_TOP_BOTTOM)
                face = face.transpose(Image.FLIP_TOP_BOTTOM)

            # epic edge case
            if char == "a":
                draw = ImageDraw.Draw(letter)
                draw.rectangle((5, 13, 8, 16), fill=(255, 255, 255, 255))

        else:

            if char in cheatletters:
                scan_line_x_coords = cheatletters[char]
            else:
                w = get_text_dimensions(char, font)[0] + 4
                random_x = random.randint(0, master_im.width - 13)
                scan_line_x_coords = [random_x, random_x + w]
                cheatletters[char] = scan_line_x_coords

            face = master_im.crop((scan_line_x_coords[0], y_coord_split, scan_line_x_coords[1], master_im.height))

            # create new blank letter template
            letter = Image.new('RGB', (face.width, y_coord_split))
            # draw white rectangle background and the letter
            draw = ImageDraw.Draw(letter)
            draw.rectangle((0, 0, letter.width, letter.height), fill=(255, 255, 255, 255))
            draw.text((0, 0), char, font=font, fill=(0, 0, 0, 255))
            # stretch the letter to match the natural stretch of the original image
            letter = letter.resize((int(letter.width * 1.75), letter.height))
            letter = letter.crop((0, 0, face.width, letter.height))
        stringsofar += char

        # combine letter and face then paste it into the final image
        scan_line = Image.new('RGB', (letter.width, letter.height + face.height))
        scan_line.paste(letter, (0, 0))
        scan_line.paste(face, (0, y_coord_split))
        final_image.paste(scan_line, (total_width, 0))

        total_width += scan_line.width
    final_image = final_image.crop((0, 0, total_width, final_image.height))
    # final_image.show()
    filename = reserve_tempfile("png")
    final_image.save(filename)
    return filename
