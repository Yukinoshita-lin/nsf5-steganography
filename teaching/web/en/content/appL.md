# Appendix L - User Guide for the Companion Tool ImageMatrix

<!-- lang-switch -->
> [🌐 中文版](https://yukinoshita-lin.github.io/nsf5-steganography/zh/content/appL.html)



This appendix is the complete guide to ImageMatrix, the companion tool of Chapter 1. It is an independent open-source project released by the same author (github.com/Yukinoshita-lin/ImageMatrix, Apache-2.0 license), and **has no dependency on the nsF5 project studied in this handbook, nor any steganography functionality**; its only purpose is to turn "an image = a matrix of numbers" from an abstraction into something you can see and modify on your own screen.

## L.1 What It Is and Why It Comes with the Handbook

In one sentence: **a bidirectional converter between pictures and numeric matrices (R/G/B/grayscale)** — written in pure C/C++, depending on no third-party libraries, with a built-in Win32 graphical interface and a command-line mode as well.

| **Capability** | **Description** |
| --- | --- |
| Open images | BMP / PNG / JPEG / GIF / TIFF; files can be dragged and dropped straight into the window |
| Export TXT matrix | Five layouts: CHANNELS / RGB / RGBA / GRAY / HEX |
| Import TXT matrix | Rebuild an image from edited matrix text; when width/height are missing, a dialog asks for the width and auto-corrects |
| Save as image | PNG / JPEG / BMP / GIF / TIFF |
| Pixel values | The status bar shows in real time the R/G/B/grayscale values and #RRGGBB of the pixel under the mouse |

It sits in Chapter 1 because it fills precisely the only "hands-on gap" at the start of this handbook: the original project tells you to "open the project and read the code", but reading the code requires knowing Python first (not taught until Chapter 2); ImageMatrix lets you verify with your own hands that "an image is a table of integers" **before learning any code**. It is the first teaching aid in this handbook for the CSAPP discipline of "get your hands on the real thing first".

## L.2 Getting and Installing It

| **Method** | **How** | **Who it is for** |
| --- | --- | --- |
| One-click installer | Download ImageMatrix_Setup.exe from the repository's Releases and double-click to install (no admin rights needed) | Anyone who just wants to run the experiments hands-on |
| Build from source | Run build.bat with MinGW-w64 to get build\imagematrix.exe and imagematrix-cli.exe | Anyone who wants to read a pure C++ project along the way |
| Run directly | The build output is a statically linked single file; copy it to another Windows machine and double-click to run | Lab machine rooms, environments without network access |

The installer unpacks the program into %LOCALAPPDATA%\Programs\ImageMatrix and automatically creates Start menu and desktop shortcuts; you can uninstall it in one click under "Settings → Apps".

## L.3 The Interface and Core Operations

![fig-17](../assets/img117.png)

Figure L-1 The main interface of ImageMatrix. The top row holds "Open image / Export to TXT / Import TXT / Save as image", plus the "Matrix format" dropdown and the "Write comment header" toggle; the central canvas supports wheel zoom and drag panning. With no material on hand the first time, click "Generate test pattern" to get a test image with color bars + grayscale + a gradient. (Screenshot from the ImageMatrix repository)

1. Open an image: click "Open image...", or drag an image straight into the window;

2. View the matrix: click "View matrix text" and the window shows a matrix text preview of the current image's numeric matrix, which you can copy to the clipboard;

3. Export: pick a layout in "Matrix format", click "Export to TXT...", and choose where to save;

4. Import: click "Import TXT..." and the program rebuilds the image from the matrix (when the # width header is missing, a dialog asks for the width);

5. Save: click "Save as image..." to store the rebuilt result as PNG / JPEG / BMP and so on.

Keyboard shortcuts: Ctrl+O to open, Ctrl+S to export TXT, Ctrl+T to import TXT, Ctrl+E to save as an image; the wheel zooms centered on the cursor, left-button drag pans, and at magnification above 8x the pixel grid is displayed.

## L.4 The Five Matrix Formats at a Glance

| **format** | **Content of each line** | **Typical use** |
| --- | --- | --- |
| GRAY | One line = one row of the image (width grayscale values) | The LSB experiments of Sections 1.2 / 1.4 (only brightness matters) |
| CHANNELS | R matrix → G matrix → B matrix → GRAY matrix | Seeing clearly that "a color image = three tables stacked together" |
| RGB | One line = one pixel: R, G, B | Looking at color pixel by pixel |
| RGBA | One line = one pixel: R, G, B, A | Images with transparency (A) |
| HEX | One line = one pixel: RRGGBB | Getting a feel for hexadecimal notation (Section 1.2) |

Exported files carry a `#` comment header declaring width / height / format / max and the grayscale formula, and it is what makes the file come back exactly on import; the grayscale formula matches the handbook: `Y = round(0.299*R + 0.587*G + 0.114*B)` (ITU-R BT.601).

## L.5 Command Line (Batch Processing and Self-Test)

```text
v = 200
build\imagematrix-cli.exe to-txt   -i photo.png -o photo.txt -f GRAY
build\imagematrix-cli.exe to-image -i photo.txt -o back.png
build\imagematrix-cli.exe info     -i photo.png
build\imagematrix-cli.exe gen      -o pattern.png -w 320 -h 240
build\imagematrix-cli.exe selftest            :: 20 项自检
```

Options: `-f RGB|RGBA|GRAY|CHANNELS|HEX`, `--no-header`, `--width N`, `-q 92` (JPEG quality). Repository tests verify that the TXT exported by the command line and by the GUI has **exactly identical SHA256 values** — this is the "consistency first" engineering discipline of Chapter 9, just applied to a much smaller program.

## L.6 How It Maps to the Handbook Chapters

| **Handbook location** | **What to do with ImageMatrix** |
| --- | --- |
| 1.1 Images as matrices | Export GRAY / CHANNELS and see with your own eyes that "an image = a table of numbers" |
| 1.2 Binary and the LSB | Change 200 into 201 in the TXT and experience an LSB flip with zero code |
| 1.4 Bit planes | Write a column of pixels out in binary and observe the regular difference between high and low bits |
| 1.5 cover / stego | Craft your first cover / stego pair by hand in Notepad |
| 2.2 Thinking about images with NumPy | Use it to see the phenomenon first, then reproduce the same array with NumPy |
| 3.2 Minimal LSB steganography | Replace the manual steps with code and compare "manual vs code" |
| 9.5 Testing and CI | Refer to its selftest and GUI smoke test (GUI and CLI output are byte-for-byte identical) |

## L.7 A Complete Hands-On Walkthrough

> **Try it |** From a photo to a pair of cover / stego (zero code the whole way)
> 
> ① Open a real photo (or click "Generate test pattern");
> 
> ② Choose the GRAY format and export it as cover.txt, then save another copy as stego.txt;
> 
> ③ Open stego.txt in Notepad and, at the agreed positions, change a few pixels to the target parity (hiding 1 → odd, hiding 0 → even);
> 
> ④ Import stego.txt and save it as stego.png;
> 
> ⑤ Put the original and stego.png side by side: indistinguishable to the naked eye.
> 
> Going further: run the Chapter 3 Python LSB script, export the output/stego_*.png it produces, then open that in ImageMatrix — you will see that what the code does is exactly what you did by hand.

One final word on the boundary: ImageMatrix helps you **see** the numbers, not **hide** them. Real nsF5 steganography — Hamming matrix encoding, magnitude reduction, wet paper coding, passphrase keying — still lives in Chapters 4, 5 and 6, to be learned step by step along the code in F:\Steganography. ImageMatrix is only the stepping stone that walks you to the door.
