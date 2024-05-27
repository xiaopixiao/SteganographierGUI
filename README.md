# SteganographierGUI
将文件隐写进MP4/MKV文件中


## 更新

### 隐写者 Ver.1.1.1 CLI

作者： 层林尽染



#### 使用说明

本程序可以将文件或文件夹隐写到视频文件中，或从视频文件中提取隐写的文件或文件夹。程序支持命令行界面 (CLI) 和图形用户界面 (GUI) 两种模式。

1. **GUI** 模式： 直接运行程序，不带任何参数。关于GUI的用法详见演示视频。

2. **CLI** 模式： 使用以下参数运行程序：

   ```
   -i, --input     指定输入文件或文件夹的路径。如果不使用任何参数标签，程序会将第一个未知参数视为输入路径。
   -o, --output    1. 指定输出文件名(包含后缀名) [或] 2. 指定输出路径(默认为原文件名+"_hidden.mp4/mkv")。
   -p, --password  设置密码 (默认无密码)。
   -t, --type      设置输出文件类型 (默认为mp4)，支持mp4和mkv两种格式。
   -c, --cover     指定外壳MP4视频（如果不指定，程序会按照以下顺序搜索：
                      - 程序同路径下的cover_video文件夹
                      - 程序所在目录
                      - 输入文件或目录的父目录）
   -r, --reveal    执行解除隐写。
   ```



#### 使用示例

1. 隐写文件：

   ```
   python Steganographier.py -i "input.txt" -o "output.mp4" -p "password" -t "mp4" -c "cover.mp4"
   python Steganographier.py -i "input.txt" -o "outputFolder" -p "password" -t "mp4" -c "cover.mp4"
   ```

2. 提取文件：

   ```
   python Steganographier.py -i "input.mp4" -r -p "password"
   ```

3. 仅指定输入文件，使用默认设置：

   ```
   python Steganographier.py "input.txt"
   ```

4. 隐写文件夹：

   ```
   python Steganographier.py -i "inputFolder" -o "outputFolder" -p "password" -t "mp4"
   python Steganographier.py -i "inputFolder" -o "output.mp4" -p "password" -t "mp4"
   ```



#### 注意事项

1. 如果没有指定输出文件路径，程序会在输入文件同目录下创建默认的输出文件，文件名为原文件名 + `_hidden.mp4/mkv`。
2. 如果指定了输出路径但没有指定文件名，程序会在指定输出路径下创建一个默认的输出文件，文件名为原文件名 + `_hidden.mp4/mkv`。
3. 如果输入路径是一个文件夹，程序将隐写整个文件夹。
4. 如果没有指定外壳MP4视频，程序会按照以下顺序搜索：
   - 程序同路径下的 `cover_video` 文件夹
   - 程序所在目录
   - 输入文件或目录的父目录
5. 程序会在程序同路径下查找 `cover_video` 文件夹。如果该文件夹存在，程序会在其中搜索 .mp4 文件。如果该文件夹不存在，程序会跳过这一步，继续在其他位置搜索。

**Full Changelog**: https://github.com/cenglin123/SteganographierGUI/compare/v1.1.0...v1.1.1

**v1.1.0 版本进位**

新增命令行调用的 CLI 模式，模式命令如下：
```
(hide) C:\Users\xxxx\>python Steganographier.py -h
usage: Steganographier.py [-h] [-i INPUT] [-o OUTPUT] [-p PASSWORD] [-t {mp4,mkv}] [-c COVER] [-r]

隐写者 Ver.1.1.0 CLI 作者: 层林尽染

options:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        输入文件/文件夹路径
  -o OUTPUT, --output OUTPUT
                        输出隐写文件的包含后缀名在内的相对路径或绝对路径
  -p PASSWORD, --password PASSWORD
                        设置密码
  -t {mp4,mkv}, --type {mp4,mkv}
                        设置输出文件类型
  -c COVER, --cover COVER
                        设置外壳MP4视频路径
  -r, --reveal          执行解除隐写
```
用法举例：
```
(hide) C:\Users\xxxx>隐写者.exe -i D:\测试\异界之美少女大召唤 -o output.mp4 -t mp4 -c D:\测试\123.mp4
```

* * *

**v1.0.10 改进：**
```
1. 隐写时会随机插入压缩文件的特征码，进一步增加混淆度  
2. 输出文件名可以选择随机文件名  
3. 外壳文件新增名称排序、随机排序、时长排序选项。
```

**v1.0.9 修改**：参数栏添加【输出名】选项，现在可以选择外壳MP4文件名作为输出文件名

**v1.0.8 改进**：新增外壳MP4文件夹选择功能，现在可以点击【选择文件夹】按钮以自行选择外壳MP4文件夹。

**v1.0.7 改进**：外壳文件菜单中的文件现在会按照时长降序排列

**v1.0.6 修改**：密码获取的逻辑变更，现在可以不指定密码

**v1.0.5 改进**：隐写时文件末尾增加随机字节，以使得每次生成的文件哈希值不同

**v1.0.4 改进**：新增外壳文件选择菜单

**v1.0.3 改进**
```
1. 隐写文件夹时现在会在压缩包内生成同名的文件夹  
2. 修改tools的判断逻辑，如果不使用mkv模式则不会弹出警告  
3. 新增mkv文件隐写大小警告（单个mkv文件不能隐写总量超过2GB的资源）  
4. 修正一些其他bug
```

**v1.0.2 新增** 隐写为mkv文件的逻辑，引入第三方工具用于处理mkv文件

```
.\tools\mkvextract.exe
.\tools\mkvinfo.exe
.\tools\mkvmerge.exe
```

**v1.0.1** 修复了无法隐写ZIP格式文件的bug


## 1. 背景

如今，国内各大网盘审查政策日趋严格，分享链接炸链的可能性越来愈大。

传统来说，我们采用**带密码的多层压缩包**来应对审查问题。这样的做法非常麻烦，并且当层数多、文件大时，频繁解压对于硬盘的损耗也是难以忽视的。围绕这个问题，过去产生了多种利用网盘特性进行**秒传**的解决方案，但是随着网盘政策的收紧，这些方案大多已经失效。

此外，随着网盘政策的变化，某些格式的压缩包在未来可能不再被允许上传，如目前百度网盘不允许上传带密码的 rar 格式压缩包。

综上，这使得研究和开发更加隐蔽的数据传输方法变得尤为重要。

  

## 2. 方法介绍：把文件隐写到MP4文件中

本程序受到[仓库文章](https://cangku.moe/archives/211591)（以下简称文章[1]）的启发，利用文件隐写技术来隐藏数据从而绕过常规审查。

隐写技术通过将数据嵌入到其他媒体文件中，使数据的存在对于普通观察者而言不可见，从而实现在不引起注意的情况下进行信息传输。

隐写技术已经有很多先例，传统做法主要有**图种**，即把数据嵌入图片中，表面上看起来是一张图片，但修改后缀名即可解压然后得到隐藏的数据。

图种的原理如下：

```sh
copy /b "图片.jpg" + "压缩包.zip" "生成目标.jpg"
```

但是这样的做法容易引起怀疑，毕竟一张清晰度分辨率都并不算高的图片居然有几个G，并且还有非常高的下载转存记录，这实在太可疑了[[1]](https://cangku.moe/archives/211591)。

因此，考虑伪装的有效性，使用MP4文件作为隐写的外壳文件更为合理一些，大视频引起怀疑的可能性显然低于大图片。

我们的目标是通过隐写伪装来降低可疑度，从而尽可能以最低的成本实现安全分享。因为假如被频繁举报，即使压缩包层数再多，密码再复杂，在已经被强烈怀疑的情况下大概也回天乏术。

**最好的防御不是叠甲，而是伪装。**

具体实现方面：将 ZIP 格式的压缩包嵌入到海绵宝宝的 MP4 视频文件中，当文件以 MP4 格式被打开时，只能看到海绵宝宝的视频，看不到 ZIP 部分；而当文件后缀名改为 ZIP 以后，解压软件（如WinRAR）可以寻找到 ZIP 部分进行正常解压。如此实现文件的安全分享。

## 3. 问题与改进

虽然文章[\[1\]](https://cangku.moe/archives/211591)提供了一个有效的代码实现用于文件隐写，但该方法缺乏一个简单易用的操作界面，这限制了其推广与普及。

本程序在文章[[1]](https://cangku.moe/archives/211591)的基础上进行简化，开发了一个包含图形用户界面（GUI）的隐写程序，使用户能够通过简单的拖放和点击操作完成文件的隐写和解隐写。

2024.4.24 新增：根据文章[[2]](https://cangku.moe/archives/199992)提出的方法，也可以把文件以附件的形式嵌入到MKV文件中，在 v1.0.2 版本中新增了此逻辑。


## 4. GUI设计与功能介绍

![image](https://github.com/cenglin123/SteganographierGUI/assets/167851968/52224be3-449c-4ead-a65e-da6a93d1e7d4)



演示视频：
[https://youtu.be/2p2ANR3q2Fg](https://youtu.be/ztjKF8FPIM0?si=rI4QANcmoU2cQEHn)

本程序允许通过**输入密码**和**拖入文件**的方式来直接进行文件的隐写和解隐写。

程序具有以下特点：

**一体化操作**：既可以进行**隐写**，也可以在同一个界面进行**解除隐写**操作，提升了程序的整体效率和便利性。

**拖放功能**：支持拖放文件或文件夹到指定区域，简化了文件选择的过程。

**通用性**：产生的隐写MP4文件也可以**手动**修改后缀名解压，**并不强制要求使用本程序**。

**密码保护**：~**必须**输入密码才能进行隐写或解隐写操作。~ (2024.4.29 于 `1.0.6` 版本中修改，现在可以不指定密码)

  

## 5. 不足与展望

目前的程序仍然存在一些问题，比如合并方法是简单地将ZIP文件附加到视频文件的末尾。这种方法虽然易于实现但也容易被检测到。

后续也许可以考虑使用一种更加隐蔽的方式，例如将ZIP文件的内容嵌入到视频文件的某些不太关键的部分，在每个I帧后插入一小段数据等。这类做法需要分析视频文件的编码细节，可能需要用到其他库如 FFmpeg 等，具体留待后续研究。

尽管如此，根据文章[\[1\]](https://cangku.moe/archives/211591)作者 [@亜璃紗](https://cangku.moe/user/272506/post) 的测试结果，**在不被特意针对性举报的情况下，这样的隐写方法已经足以认为是一个可以推广的解决方案了**。

今后随着技术的进一步完善，此类隐写方法或许能成为替代秒传链接的一个有效手段。

**此程序权当抛砖引玉，目前测试仍不充分，可能有bug，欢迎各位积极参与研究**。



## 免责声明:

<font color="#c0504d"><b>本程序仅用于保护个人信息安全，请勿用于任何违法犯罪活动</b></font>

<font color="#c0504d"><b>否则[后果](https://mps.gjzwfw.gov.cn/)自负，开发者对此不承担任何责任</b></font>

