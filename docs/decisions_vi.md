# Các quyết định của dự án

## IMPORTANT — Hợp đồng Observation chuẩn dùng chung giữa các bộ dữ liệu

**Quyết định:** Áp dụng hợp đồng observation thô chuẩn sau đây cho pipeline nhập dữ liệu ban đầu của XJTU-SY và NASA IMS:

```text
Observation {
  dataset_name: string,
  experiment_id: string,
  bearing_id: string,
  measurement_index: integer,
  elapsed_time_sec: float,

  rotational_speed_rpm: float,
  radial_load_kn: float,

  channel_id: string,
  channel_direction: enum(horizontal, vertical, unknown),
  sampling_rate_hz: float,
  signal_length: integer,
  vibration_signal: float32[]
}
```

**Ngày:** 2026-10-05

**Vấn đề được giải quyết:** XJTU-SY và IMS có cấu trúc tệp nguồn khác nhau. XJTU-SY lưu một snapshot của vòng bi với các cột ngang/dọc, trong khi IMS có nhiều thí nghiệm và một tệp nguồn có thể chứa nhiều cột vòng bi/kênh. Nếu hợp đồng phụ thuộc vào bố cục tệp, hệ thống sẽ làm mất thông tin nhận diện kênh/vòng bi hoặc buộc phần code dành riêng cho từng bộ dữ liệu phải xuất hiện trong mô hình.

**Trạng thái hệ thống hiện tại:** Dự án chưa có phần triển khai nhập dữ liệu. Nền tảng nghiên cứu trước đây mô tả một `Observation` tổng quát dưới dạng `{asset_id, timestamp, features, condition}`; quyết định này thay thế phần mô tả tạm đó bằng hợp đồng observation thô đã chuẩn hóa và không mất dữ liệu. `TrajectoryTask` vẫn là đối tượng huấn luyện được suy ra từ dữ liệu.

**Yêu cầu nghiệp vụ/dự án:**
- Có một quy trình nạp dữ liệu có thể tái lập cho cả hai bộ dữ liệu ban đầu.
- Giữ lại tín hiệu rung thô để có thể tính toán lại các đặc trưng.
- Hỗ trợ chia tập train/validation/test theo từng vòng bi.
- Biểu diễn lịch sử thưa và không đều mà không làm rò rỉ tỷ lệ vòng đời.
- Giữ lại ngữ cảnh vận hành để thích ứng giữa các miền có kiểm soát.
- Không để các đặc thù của từng nguồn dữ liệu lọt vào code mô hình.

**Các phương án đã cân nhắc:**
1. Duy trì schema riêng cho XJTU-SY và IMS. Không chọn vì code xử lý trajectory/task/mô hình phía sau sẽ bị lặp lại, đồng thời việc kiểm tra khả năng thích ứng giữa các bộ dữ liệu sẽ khó hơn.
2. Xem mỗi tệp nguồn là một observation. Không chọn vì tệp IMS có thể chứa nhiều vòng bi/kênh.
3. Chỉ dùng hợp đồng gồm các đặc trưng đã trích xuất. Không chọn vì sẽ mất nguồn gốc dạng sóng thô và khả năng tái lập quy trình trích xuất đặc trưng.
4. Thêm `relative_time_sec` vào observation thô. Không chọn vì thời gian tương đối phụ thuộc vào mốc neo do task lựa chọn.
5. Bắt buộc các trường chỉ có ở một số nguồn như `source_timestamp`, `sensor_id` và `signal_unit`. Không chọn vì các trường này không có sẵn hoặc không được tài liệu hóa đồng nhất ở cả hai bộ dữ liệu.

**Lập luận:** Schema được chọn là phần giao nhau nhỏ nhất về mặt ngữ nghĩa mà cả hai adapter đều có thể tạo ra mà không mất dữ liệu. `experiment_id` phân biệt điều kiện/thí nghiệm; `bearing_id` hỗ trợ chia tập ở cấp tài sản; `measurement_index` và `elapsed_time_sec` giữ nguyên thứ tự thời gian; tốc độ/tải trọng lưu ngữ cảnh vận hành vật lý; `channel_id` và `channel_direction` giữ lại chiều cảm biến; tần số lấy mẫu, độ dài và dạng sóng giúp quy trình xử lý tín hiệu có thể tái lập. Các trường có thể được suy ra từ metadata của thí nghiệm hoặc tên tệp nguồn — hợp đồng mô tả bộ dữ liệu đã chuẩn hóa, không phải các cột nguyên bản.

**Bằng chứng và giả định:**
- Tài liệu XJTU-SY mô tả 15 vòng bi chạy đến hỏng, ba điều kiện tốc độ/tải trọng, hai gia tốc kế (ngang và dọc), tần số lấy mẫu 25,6 kHz, 32.768 điểm cho mỗi snapshot và một tệp CSV cho mỗi lần lấy mẫu: <https://www.researchgate.net/profile/Biao-Wang-27/publication/338596319_XJTU-SY_Bearing_Datasets/data/5eb689ee299bf1287f77f443/Introduction-to-XJTU-SY-Bearing-Dataset-NEW.pdf>
- Kho dữ liệu chính thức của NASA xác định IMS là bộ dữ liệu vòng bi do IMS/University of Cincinnati cung cấp và liên kết đến tệp lưu trữ: <https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/>
- Tốc độ vận hành và tải trọng được xem là metadata cấp thí nghiệm, chuẩn hóa về RPM và kN.
- `signal_length` là trường dùng để kiểm tra hợp lệ và phải bằng độ dài của dạng sóng.
- Adapter sẽ tạo một dòng đã chuẩn hóa cho mỗi tổ hợp vòng bi × phép đo × kênh, kể cả khi một tệp nguồn chứa nhiều kênh.

**Hệ quả:**
- Tích cực: Có chung một giao diện nhập dữ liệu và trajectory; giữ lại dạng sóng thô; hỗ trợ chia tập có xét đến kênh và vòng bi; tách thời gian tương đối theo task khỏi thời gian của nguồn.
- Tiêu cực: Adapter phải xác định ánh xạ nguồn sang vòng bi/kênh; metadata thí nghiệm có thể cần được lặp lại hoặc ghép nối; một số thông tin đặc thù của nguồn nằm ngoài hợp đồng cốt lõi; dạng sóng thô có thể chiếm nhiều dung lượng.
- Hợp đồng này được thiết kế có chủ đích cho tầng dữ liệu thô; vector đặc trưng thuộc tầng observation/task được suy ra.

**Điều kiện xem xét lại:**
- Bổ sung một bộ dữ liệu đích không thể cung cấp danh tính vòng bi, thứ tự thời gian hoặc dạng sóng rung mà không có chiến lược adapter rõ ràng.
- Việc kiểm tra tệp lưu trữ cho thấy giả định về ánh xạ kênh hoặc metadata vận hành là không đúng.
- Yêu cầu mô hình trong tương lai cần một đơn vị dữ liệu nguyên tử khác (ví dụ: observation đa kênh dưới dạng một tensor) và việc chuyển đổi vẫn bảo toàn dữ liệu.
- Dự án chính thức mở rộng ra ngoài các bộ dữ liệu vòng bi rung; khi đó cần phiên bản hóa hợp đồng thay vì âm thầm thay đổi nó.
