# Tài liệu tham chiếu dataset XJTU-SY

Tài liệu này ghi lại các thông tin nguồn được trích từ `data/raw/XJTU-SY_Bearing_Datasets/Data/XJTU-SY_Bearing_Datasets/Introduction_to_XJTU-SY_Bearing_Dataset.pdf`. Đây là tài liệu tham chiếu, không thay thế cho các quyết định chuẩn của dự án.

## Thông tin nguồn

- Đơn vị cung cấp: Xi'an Jiaotong University và Changxing Sumyoung Technology.
- Model bearing được thử nghiệm: LDK UER204.
- Sensor: hai accelerometer PCB 352C33 đặt lệch nhau 90 độ; hai channel horizontal và vertical.
- Tần số lấy mẫu: 25,6 kHz.
- Cửa sổ ghi: 32.768 mẫu, 1,28 giây, lặp lại mỗi 1 phút.
- Mỗi lần sampling được lưu thành một CSV; cột 1 là tín hiệu rung horizontal và cột 2 là tín hiệu rung vertical.
- Thí nghiệm tiếp tục đến khi biên độ cực đại horizontal hoặc vertical vượt 10 * A_h, trong đó A_h là biên độ cực đại trong giai đoạn vận hành bình thường.

## Metadata từ Bảng 2

| Condition | Bearing | Số CSV | Lifetime công bố | Fault element |
|---|---|---:|---:|---|
| condition_1 / 35 Hz / 12 kN | Bearing1_1 | 123 | 2 giờ 3 phút | Outer race |
| condition_1 / 35 Hz / 12 kN | Bearing1_2 | 161 | 2 giờ 41 phút | Outer race |
| condition_1 / 35 Hz / 12 kN | Bearing1_3 | 158 | 2 giờ 38 phút | Outer race |
| condition_1 / 35 Hz / 12 kN | Bearing1_4 | 122 | 2 giờ 2 phút | Cage |
| condition_1 / 35 Hz / 12 kN | Bearing1_5 | 52 | 52 phút | Inner race and outer race |
| condition_2 / 37.5 Hz / 11 kN | Bearing2_1 | 491 | 8 giờ 11 phút | Inner race |
| condition_2 / 37.5 Hz / 11 kN | Bearing2_2 | 161 | 2 giờ 41 phút | Outer race |
| condition_2 / 37.5 Hz / 11 kN | Bearing2_3 | 533 | 8 giờ 53 phút | Cage |
| condition_2 / 37.5 Hz / 11 kN | Bearing2_4 | 42 | 42 phút | Outer race |
| condition_2 / 37.5 Hz / 11 kN | Bearing2_5 | 339 | 5 giờ 39 phút | Outer race |
| condition_3 / 40 Hz / 10 kN | Bearing3_1 | 2538 | 42 giờ 18 phút | Outer race |
| condition_3 / 40 Hz / 10 kN | Bearing3_2 | 2496 | 41 giờ 36 phút | Inner race, ball, cage and outer race |
| condition_3 / 40 Hz / 10 kN | Bearing3_3 | 371 | 6 giờ 11 phút | Inner race |
| condition_3 / 40 Hz / 10 kN | Bearing3_4 | 1515 | 25 giờ 15 phút | Inner race |
| condition_3 / 40 Hz / 10 kN | Bearing3_5 | 114 | 1 giờ 54 phút | Outer race |

## Quy tắc diễn giải của dự án

- `fault_element` là metadata cấp trajectory, không phải nhãn `fault_state` theo timestamp.
- Giữ nguyên cách viết trong PDF ở `fault_element_raw`; nếu chuẩn hóa thì lưu riêng dưới dạng danh sách như `fault_elements`.
- Giữ lifetime công bố tách biệt với `elapsed_time_sec` của Observation.
- PDF mô tả cửa sổ kỳ vọng 32.768 mẫu. Parser raw của dự án vẫn giữ độ dài waveform thực tế và không loại file chỉ vì lệch độ dài nhỏ.
- Tên CSV dạng số vẫn là số thứ tự measurement nguồn. Quy ước của dự án là `elapsed_time_sec = (measurement_index - 1) * 60`.

## Nguồn

`data/raw/XJTU-SY_Bearing_Datasets/Data/XJTU-SY_Bearing_Datasets/Introduction_to_XJTU-SY_Bearing_Dataset.pdf`