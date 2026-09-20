# FM Newgen Face Installer — Hướng dẫn tiếng Việt

[English](../README.md) · [Tải bản Windows](https://github.com/leedontbeshy/FM-Newgen-Face-Installer/releases)

Utility Windows cho Football Manager 2024: chọn ảnh có sẵn, nhập Player Unique ID,
lưu thành `<ID>.png` và cập nhật mapping khi cần. App không tạo khuôn mặt, không
gửi dữ liệu lên mạng và không sửa save game.

## Chạy ứng dụng

Tải ZIP Windows x64 từ Releases, giải nén **toàn bộ**, rồi mở
`FMNewgenFaceInstaller.exe`. Giữ nguyên thư mục `_internal` đi kèm.
Máy chạy bản portable không cần cài Python.

Giao diện theo tỷ lệ hiển thị của Windows, dùng hai cột khi cửa sổ rộng và xếp
dọc khi cửa sổ hẹp. Chữ và preview tăng theo không gian cửa sổ; các nút cài/sửa/xóa
luôn nằm ngoài vùng cuộn. Bạn có thể đổi ID, chọn ảnh mới và cài nhiều face liên
tiếp trong cùng một lần mở app.

Bản phát hành hiện chưa ký số. Windows Smart App Control/chính sách doanh nghiệp
có thể chặn file; không tắt bảo vệ để chạy app. Checksum giúp kiểm tra file tải về,
không thay thế chữ ký số. Đọc release notes để biết kết quả kiểm thử bản đóng gói.

## Cài face

1. Lần đầu mở, chọn thư mục chứa trực tiếp ảnh và `config.xml` mà FM đang đọc,
   ví dụ `Documents\Sports Interactive\Football Manager 2024\graphics\Custom Faces`.
   Đây là graphics folder của user data, không phải thư mục cài game.
2. Nhập Player Unique ID, chỉ dùng chữ số. Khoảng trắng ngoài cùng được trim.
3. Chọn **Newgen (FM24)** cho cầu thủ game tạo; **Real player** cho cầu thủ thật.
4. Bấm **Select Image**, kiểm tra preview và filename, rồi **Install Face**.
5. Clear Cache nếu cần, sau đó Reload Skin trong FM.

Ảnh PNG/JPG/JPEG/WEBP tĩnh được lưu thành `<ID>.png`, giữ kích thước và alpha.
App không resize ảnh cài đặt; chỉ thay đổi kích thước preview. File picker ưu tiên Downloads,
sau đó nhớ thư mục chọn ảnh gần nhất.

Newgen FM24 cần `r-` ở target, nhưng tên ảnh vẫn chỉ là ID:

```xml
<record from="2002999999" to="graphics/pictures/person/r-2002999999/portrait"/>
```

Ảnh tương ứng là `2002999999.png`. Cầu thủ thật không có `r-` ở target.

| Hiện trạng | Hành vi |
| --- | --- |
| Chưa có ảnh/mapping | Cài ảnh và thêm một mapping |
| Có cả hai, mapping đúng | Hỏi Replace; chỉ thay ảnh, config không ghi lại |
| Có mapping, thiếu ảnh | Tạo lại ảnh, giữ config |
| Có ảnh, thiếu mapping | Hỏi trước khi thay ảnh và tạo mapping |
| Newgen có mapping theo kiểu cầu thủ thật | Hướng dẫn dùng Fix Mapping |
| Cancel | Không thay ảnh hoặc config |

## Fix Mapping và Remove Face

Với newgen đã cài bằng mapping cũ: nhập ID, chọn **Newgen (FM24)**, bấm
**Fix Mapping** rồi xác nhận. App chỉ sửa target của đúng ID đó, có backup;
không đổi tên/thay ảnh hoặc sửa các mapping khác. Mapping đã đúng là no-op.
Không tự sửa record có custom target hoặc nhiều record trùng `from`.

**Remove Face** chỉ cần ID, không cần chọn ảnh. Sau khi xác nhận, app xóa ảnh
và/hoặc mapping đang tồn tại. Nếu không có cả hai: **Nothing to remove**.

## Settings và reload skin

**Settings** hiển thị thư mục hiện tại, **Change Folder**, **Open Face Folder**.
Settings/log lưu tại `%LOCALAPPDATA%\FM Newgen Face Installer`.
App nhớ folder qua các lần mở. `Ctrl+O`: chọn ảnh; `Ctrl+Enter`: install.

Trong FM: **Preferences → Advanced → Interface**, tắt **Use caching to decrease
page loading times**, bật **Reload skin when confirming changes in Preferences**,
rồi **Confirm / Reload Skin**. Nếu còn ảnh cũ, **Clear Cache** rồi reload.
Tên/vị trí nút tùy ngôn ngữ và skin. Kiểm tra đúng ID, player type và user-data
folder; các facepack khác có thể chứa mapping cạnh tranh.

## An toàn với config lớn

Lookup theo luồng, dừng khi thấy ID. Không DOM/pretty-print/sort. Khi cần sửa,
app giữ nguyên byte cũ, encoding, BOM, CRLF/LF và thứ tự; tạo `.bak`, stream sang
`.tmp`, flush/fsync, validate rồi atomic replace. Bộ test dùng dữ liệu giả đến
500.000 mapping. Replace ảnh với mapping đúng không ghi lại config.

XML bất thường sẽ bị từ chối. Nếu bị kill/mất điện, có thể còn `.tmp` hoặc ảnh
phục hồi `.fm-face-*`; không tự đổi tên `.tmp` thành config khi chưa kiểm tra.
Ảnh và config không thể commit cùng lúc bằng một thao tác filesystem; lỗi bình
thường có rollback, nhưng mất điện giữa hai commit có thể để lại ảnh thiếu/thừa.
Không sửa config đồng thời bằng editor khác. Xem [giới hạn đầy đủ](../README.md#limits-and-recovery).

## Development và build

Python 3.11+ có Tcl/Tk, trên Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe -m pytest -q
.\build.ps1
```

Build tạo ZIP portable ở `dist`. Xem [hướng dẫn đóng góp](../CONTRIBUTING.md).
Mã nguồn dùng MIT; không kèm facepack, ảnh cá nhân hay config thật của người dùng.
