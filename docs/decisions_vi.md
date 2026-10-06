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


## IMPORTANT — Define experiment protocol nhân quả cho bài toán dự báo XJTU

**Quyết định:** Dùng protocol nhân quả, chia nhóm theo bearing cho giai đoạn dự báo và fault generation ban đầu trên XJTU-SY. XJTU-SY là bộ dữ liệu hiện tại; IMS để dành cho đánh giá cross-dataset riêng. Model nhận lịch sử sensor gần đây và dự đoán chuỗi tương lai có độ dài thay đổi tới khi hỏng, không nhận condition metadata hoặc tuổi vòng đời tuyệt đối.

**Ngày:** 2026-10-07

**Vấn đề được giải quyết:** Chia snapshot/window ngẫu nhiên, thời gian vòng đời tuyệt đối, tổng độ dài trajectory, thời điểm hỏng và condition ID phòng thí nghiệm có thể khiến model học shortcut từ identity bearing hoặc cấu trúc thí nghiệm thay vì học hành vi tín hiệu tương lai. Vận hành thực tế có thể có condition thay đổi, quan sát không đều và tuổi thọ giữa các bearing khác nhau lớn.

**Trạng thái hệ thống hiện tại:** Hợp đồng Observation thô đã cố định. XJTU-SY được dùng để đánh giá tổng quát hóa giữa bearing instance và giữa condition. Tất cả bearing XJTU cùng nominal model, nên đây chưa phải chuyển giữa các model bearing.

**Yêu cầu nghiệp vụ/dự án:** Dùng lịch sử sensor gần đây; hỗ trợ quan sát không đều mà không nội suy waveform thiếu; hỗ trợ horizon cấu hình và rollout tới failure; dự đoán sensor tương lai, lag tương đối, fault state tại từng thời điểm và confidence; tách tổng quát hóa giữa bearing instance khỏi condition; giữ riêng đánh giá XJTU → IMS.

**Protocol:**

1. Tại anchor t, dùng tối đa 20 bản ghi hợp lệ trong 30 phút trước đó (max_records = 20; max_lookback = 1800 giây). Mỗi bản ghi gồm tín hiệu sensor, lag_from_now và mask cho padding hoặc channel/bản ghi không có. Horizontal và vertical cùng timestamp là các kênh của một lần đo. Protocol chính yêu cầu tối thiểu 10 bản ghi; context 1–9 được đánh giá robustness riêng. Không nội suy dữ liệu thiếu.
2. Loại condition metadata, dataset_name, experiment_id, bearing_id, tên/đường dẫn file, thời gian bắt đầu tuyệt đối, tổng tuổi vận hành, measurement_index, tổng độ dài trajectory, remaining life và thời điểm hỏng thật khỏi input. Speed/load giữ trong dữ liệu thô để truy xuất nhưng loại khỏi baseline input. Preprocessing học được chỉ fit trên train.
3. Output là chuỗi bản ghi tương lai có độ dài thay đổi. Mỗi bản ghi gồm tín hiệu sensor tương lai, khoảng cách thời gian tương lai, fault_state tại thời điểm đó và confidence. Kết thúc bằng failure_event = 1 hoặc END_OF_TRAJECTORY. Horizon hữu hạn được hỗ trợ như rollout bị cắt. terminal_fault_type là target cấp trajectory, tách khỏi fault_state vì XJTU không có nhãn fault type đáng tin cậy cho từng timestamp.
4. Với mỗi anchor, lấy observation tương lai theo thứ tự đến bản ghi failure; observation tương lai không bao giờ là input. Final fault metadata có thể dùng supervision nhưng không được làm input. Confidence là một phần interface; loss và calibration để ở bước thiết kế model.
5. XJTU có hai track: unseen bearing trong cùng condition, grouped leave-one-bearing-out với inner grouped validation; và unseen condition, leave-one-condition-out, giữ cả năm bearing của một condition làm test, validation chỉ từ condition nguồn và xoay condition test qua cả ba condition. Chia toàn bộ trajectory trước khi tạo window/feature/synthetic record; cấm random split window chồng lấn. Không lấy trajectory validation/test để tạo synthetic cho train.
6. Báo cáo theo bearing, condition, fault state/type, độ dài history và forecast horizon; có persistence, autoregressive baseline, canary leakage và kiểm tra window trùng/gần trùng. XJTU → IMS là zero-shot transfer riêng trừ khi adaptation được khai báo.

**Các phương án đã cân nhắc:** Chia snapshot/window ngẫu nhiên, condition metadata, biến thời gian vòng đời tuyệt đối, history không giới hạn, nội suy waveform thiếu, output độ dài cố định và dùng terminal fault type làm nhãn timestamp-level đều bị loại vì leakage, không phù hợp triển khai, tạo tín hiệu giả hoặc gây supervision mơ hồ.

**Lập luận:** Chia theo bearing ngăn leakage từ identity và snapshot lân cận. History giới hạn với lag tương đối phù hợp triển khai nhân quả. Hai track XJTU tách biến thiên bearing instance khỏi condition trước khi đưa domain shift bên ngoài. Termination event làm rõ dự báo tới khi hỏng nhưng vẫn giữ horizon hữu hạn. Tách fault_state khỏi terminal_fault_type phân biệt trạng thái tại thời điểm với cơ chế hỏng cuối cùng.

**Bằng chứng và giả định:** XJTU-SY mô tả 15 bearing chạy đến hỏng trong ba condition, năm bearing mỗi condition và cùng nominal model: <https://github.com/WangBiaoXJTU/xjtu-sy-bearing-datasets> và <https://www.researchgate.net/profile/Biao-Wang-27/publication/338596319_XJTU-SY_Bearing_Datasets/data/5eb689ee299bf1287f77f443/Introduction-to-XJTU-SY-Bearing-Dataset-NEW.pdf>. Observation xấp xỉ mỗi phút; fault metadata được xem là thông tin fault cuối trajectory trừ khi có quy trình gán nhãn theo timestamp được tài liệu hóa.

**Hệ quả:** Ranh giới leakage và phạm vi đánh giá rõ ràng; hỗ trợ history không đều, horizon cấu hình, tổng quát hóa cùng condition và condition chưa thấy. Protocol cần grouped manifest, inner validation, mask, termination và tổng hợp theo bearing. Không quy định kiến trúc neural hoặc confidence loss.

**Điều kiện xem xét lại:** Condition metadata đáng tin cậy luôn có sẵn; validation cho thấy cửa sổ 30 phút/20 record không đại diện; có quy trình gán nhãn fault theo timestamp được kiểm chứng làm thay đổi fault_state; hoặc dataset/model bearing mới cần protocol transfer phiên bản hóa riêng.
