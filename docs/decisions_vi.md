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

## IMPORTANT — Quy định chronology khi parse XJTU-SY và chính sách độ dài waveform

**Quyết định:** Với XJTU-SY, hiểu số trong tên CSV là số thứ tự measurement nguồn: `n.csv` là lần đo thứ `n`, cách lần đo trước xấp xỉ một phút. Giữ nguyên giá trị này trong `measurement_index`. Chuẩn hóa thời gian đã trôi qua, lấy measurement 1 của nguồn làm mốc, theo công thức `elapsed_time_sec = (measurement_index - 1) * 60`. Giữ độ dài waveform thực tế trong `signal_length`; không loại file chỉ vì độ dài khác 32.768 mẫu. Parser raw phải giữ nguyên các mẫu đã đọc. Nếu cần sửa cục bộ một số mẫu thiếu, đó là bước tiền xử lý riêng và không được ghi đè biểu diễn raw.

**Ngày:** 2026-10-08

**Vấn đề được giải quyết:** CSV XJTU-SY không có timestamp tường minh, và độ dài waveform có thể thay đổi theo tần số lấy mẫu thực tế hoặc do mất một lượng nhỏ mẫu khi thu thập. Nếu xem thứ tự tên file như một index mới, bắt buộc mọi waveform dài đúng 32.768 mẫu, hoặc sửa dữ liệu ngay khi parse raw, ta sẽ làm mờ provenance và trộn lẫn ingestion với tiền xử lý.

**Trạng thái hệ thống hiện tại:** Hợp đồng `Observation` chuẩn và protocol thí nghiệm nhân quả đã cố định. Cây raw XJTU-SY có một CSV cho mỗi measurement, với các cột tín hiệu ngang và dọc. Việc kiểm tra ban đầu cho thấy các file mẫu có 32.768 dòng dữ liệu, nhưng đây không phải yêu cầu cứng của parser.

**Yêu cầu nghiệp vụ/dự án:** Bảo toàn chronology và provenance của bearing; hỗ trợ measurement bị thiếu hoặc không đều; giữ tín hiệu raw để tái lập xử lý phía sau; không loại bỏ record còn dùng được chỉ vì lệch độ dài nhỏ; mọi bước điền/sửa dữ liệu phải có thể kiểm tra và hoàn nguyên.

**Các phương án đã cân nhắc:**
1. Dùng `measurement_index * 60` làm thời gian đã trôi qua. Không chọn cho biểu diễn trajectory chuẩn hóa vì measurement 1 của nguồn nên là mốc thời gian 0; số phút nguồn vẫn được giữ trong `measurement_index`.
2. Đánh lại số file sau khi phát hiện khoảng trống. Không chọn vì sẽ che giấu measurement bị thiếu và làm hỏng chronology nguồn.
3. Bắt buộc đúng 32.768 mẫu. Không chọn vì độ dài phụ thuộc vào quá trình thu thập và một sai lệch nhỏ không nhất thiết làm measurement không dùng được.
4. Nội suy hoặc padding ngay khi parse raw. Không chọn vì tầng raw phải bảo toàn dữ liệu và chính sách tiền xử lý cần được kiểm thử độc lập.
5. Nội suy measurement bị thiếu. Không chọn vì observation bị thiếu trong một phút là khoảng trống thời gian thực, không phải waveform bị thiếu mẫu.

**Lập luận:** Tên file là chronology nguồn duy nhất hiện có của XJTU-SY, nên phải giữ nguyên giá trị số của nó. Lấy measurement 1 của nguồn làm mốc 0 giúp `elapsed_time_sec` là thời gian tương đối của trajectory nhưng vẫn giữ số phút nguyên bản. Một lần thu khoảng 1,28 giây ở 25,6 kHz cho 32.768 mẫu là giá trị kỳ vọng, không phải hợp đồng tuyệt đối. Giữ độ dài và mẫu raw thực tế tránh tạo dữ liệu giả; bước làm sạch sau này có thể đưa ra quyết định hẹp, có kiểm toán về việc sửa cục bộ một số mẫu.

**Bằng chứng và giả định:** Cây XJTU-SY dùng tên CSV dạng số như `1.csv`, `2.csv`, `100.csv`; các file đã kiểm tra có cột tín hiệu ngang và dọc. Quy trình thu dữ liệu là xấp xỉ một measurement mỗi phút và xấp xỉ 1,28 giây mỗi measurement ở 25,6 kHz. CSV bị thiếu được xem là observation bị thiếu; waveform ngắn hoặc thiếu cục bộ được xem là vấn đề chất lượng tín hiệu cần báo cáo riêng.

**Hệ quả:** Parser có thể giữ chronology mà không cần timestamp, chấp nhận sai lệch độ dài hợp lệ và không thay đổi raw data. Manifest và validation report phải ghi nhận measurement number bị thiếu, độ dài thực tế của tín hiệu và các bất thường khi parse. Nếu bổ sung bước sửa cục bộ sau này, cần quy định rõ ngưỡng, mask và provenance.

**Điều kiện xem xét lại:** Dataset cung cấp timestamp có thẩm quyền; cadence một phút được chứng minh là sai lệch đáng kể hoặc không đều; metadata thu thập cho thấy waveform ngắn là do truncation chứ không phải sai lệch nhỏ; hoặc phân tích phía sau cần một mốc thời gian khác. Việc sửa trực tiếp raw sample sẽ phải làm lại quyết định này.
## IMPORTANT — Chuẩn hóa metadata XJTU-SY thành các lớp riêng có nguồn

**Quyết định:** Lưu metadata XJTU-SY bên ngoài bảng Observation raw chuẩn thành ba lớp: một dòng metadata dataset, ba dòng metadata condition và một dòng metadata trajectory cho mỗi bearing. Dùng `configs/xjtu_trajectory_metadata.csv` làm bảng mapping nguồn có thể chỉnh sửa cho metadata trajectory từ Bảng 2. Tạo các output Parquet từ mapping này và source manifest đã parse. Giữ `fault_element_raw` và `reported_lifetime_raw`; lưu riêng `fault_elements` đã chuẩn hóa dưới dạng danh sách. Suy ra số measurement đã parse và biên index từ manifest. Không tạo nhãn `fault_state` theo timestamp từ PDF.

**Ngày:** 2026-10-08

**Vấn đề được giải quyết:** PDF cung cấp thông tin về dataset, condition, lifetime, số file và fault element của bearing, nhưng các trường này có phạm vi khác nhau và không được trộn vào hợp đồng Observation raw hoặc coi là supervision theo timestamp.

**Trạng thái hệ thống hiện tại:** CSV raw XJTU-SY đã được parse thành `xjtu_observations.parquet` và `xjtu_source_manifest.parquet`. Bảng 2 trong PDF có metadata của cả 15 bearing. Phần chuẩn hóa tạo `xjtu_dataset_metadata.parquet`, `xjtu_condition_metadata.parquet`, `xjtu_trajectory_metadata.parquet` và `xjtu_metadata_report.json` trong `data/interim/xjtu/`.

**Yêu cầu nghiệp vụ/dự án:** Giữ nhãn nguồn và provenance có thể kiểm tra; hỗ trợ EDA ở cấp condition và trajectory; phân biệt lifetime được công bố với elapsed time của Observation; hỗ trợ fault element nhiều nhãn đã chuẩn hóa; ngăn metadata rò rỉ vào baseline model input; cho phép review mapping thủ công mà không phải sửa code parser.

**Các phương án đã cân nhắc:**
1. Đưa toàn bộ metadata vào từng Observation raw. Không chọn vì phạm vi metadata khác nhau và hợp đồng raw chuẩn cần ổn định, không mất dữ liệu.
2. Parse PDF tại runtime. Không chọn vì trích xuất PDF dễ không ổn định và các chỉnh sửa thủ công cần được thể hiện rõ, có thể review.
3. Chỉ lưu nhãn fault đã chuẩn hóa. Không chọn vì phải giữ lại cách viết và provenance của nguồn.
4. Dùng `reported_lifetime_min` làm `elapsed_time_sec` của Observation. Không chọn vì lifetime công bố và quy ước thời gian tương đối của trajectory là hai khái niệm khác nhau.
5. Suy ra fault state theo timestamp từ fault element cuối trajectory. Không chọn vì PDF chỉ cung cấp thông tin fault cấp trajectory, không có nhãn timestamp đáng tin cậy.

**Lập luận:** CSV mapping nhỏ, có thể chỉnh sửa, phù hợp làm nguồn sự thật cho mapping 15 dòng từ Bảng 2; Parquet phù hợp cho xử lý dữ liệu phía sau. Tách bảng dataset, condition và trajectory làm rõ phạm vi. Ghép trajectory metadata với manifest giúp lấy số lượng và biên measurement đã parse mà không sửa Observation raw. Giữ nhãn raw cạnh nhãn chuẩn hóa bảo toàn khả năng kiểm toán và vẫn thuận tiện sử dụng.

**Bằng chứng và giả định:** PDF nguồn ghi nhận 15 bearing, ba condition, metadata sampling, lifetime công bố, số CSV và fault element trong Bảng 2. Manifest hiện tại có đủ 9.216 file nguồn với key bearing/condition khớp và không có sai lệch số lượng. `fault_elements` dùng vocabulary kiểm soát gồm `inner_race`, `outer_race`, `cage` và `ball`.

**Hệ quả:** Có thể sửa metadata trong CSV cấu hình rồi tạo lại output. Code phía sau phải join bằng `dataset_name`, `experiment_id` và `bearing_id`. File mapping và các Parquet đã tạo cần được giữ đồng bộ. Metadata sẵn sàng cho EDA và tạo target nhưng bị loại khỏi baseline model input theo experiment protocol.

**Điều kiện xem xét lại:** Tài liệu dataset có thẩm quyền được cập nhật làm thay đổi Bảng 2; có quy trình gán nhãn theo timestamp được kiểm chứng; metadata cần hỗ trợ dataset khác có phạm vi không tương thích; hoặc dự án cần ontology metadata có version vượt ra ngoài bốn fault-element hiện tại.
## IMPORTANT — Dùng 11 mốc chuẩn hóa trajectory cho FFT EDA XJTU-SY

**Quyết định:** EDA XJTU-SY sẽ tính các thống kê miền tần số tại 11 mốc chuẩn hóa của trajectory: 0%, 10%, 20%, ..., 100%. Mốc 0% là measurement nguồn đầu tiên và mốc 100% là measurement nguồn cuối cùng của từng bearing. Các mốc ở giữa chọn measurement gần nhất theo vị trí trong trajectory, dựa trên các observation đã sắp xếp của bearing đó; số measurement nguồn được chọn phải được lưu trong output EDA.

**Ngày:** 2026-10-08

**Vấn đề được giải quyết:** Các trajectory XJTU-SY có số measurement rất khác nhau. Nếu chọn cùng một số measurement tuyệt đối, các FFT sẽ đại diện cho các giai đoạn vòng đời khác nhau giữa các bearing.

**Trạng thái hệ thống hiện tại:** Observation raw và trajectory metadata đã được chuẩn hóa. Phạm vi EDA gồm thống kê miền thời gian cho toàn bộ measurement và thống kê miền tần số tại các mốc đại diện. Chưa tạo output FFT.

**Yêu cầu nghiệp vụ/dự án:** So sánh diễn biến phổ tần giữa bearing, condition, channel và fault element cấp trajectory, đồng thời giữ nguyên measurement index nguồn và không nội suy hoặc tạo observation giả.

**Các phương án đã cân nhắc:**
1. Chỉ dùng measurement đầu, giữa và cuối. Không chọn vì quá thô để quan sát diễn biến phổ theo thời gian.
2. Dùng các measurement index tuyệt đối cố định. Không chọn vì trajectory có lifetime và số file khác nhau.
3. Resample hoặc nội suy mọi trajectory về cùng độ dài. Không chọn vì sẽ tạo observation waveform tổng hợp và làm mờ chronology nguồn.
4. Tính FFT cho mọi measurement. Tạm thời chưa chọn vì tăng chi phí tính toán và dung lượng mà chưa cần cho vòng EDA so sánh đầu tiên.

**Lập luận:** 11 vị trí chuẩn hóa cách đều tạo ra cùng một lưới vòng đời để so sánh giữa các trajectory nhưng không thay đổi waveform nguồn. Chọn measurement gần nhất là quyết định tất định, có thể kiểm tra và không tạo dữ liệu giả. Lưu cả mốc chuẩn hóa và `measurement_index` giúp kết quả có thể diễn giải.

**Bằng chứng và giả định:** Bảng 2 của tài liệu XJTU-SY cho thấy độ dài trajectory khác nhau đáng kể, từ 42 đến 2.538 CSV. Mỗi CSV chứa waveform horizontal và vertical của một lần sampling.

**Hệ quả:** Output EDA phải có `anchor_fraction`, `selected_measurement_index`, `channel_id` và các trường thống kê FFT. Với trajectory rất ngắn, hai mốc gần nhau có thể chọn cùng một measurement; điều này được chấp nhận và phải được ghi nhận thay vì che giấu.

**Điều kiện xem xét lại:** Task phía sau yêu cầu cách căn chỉnh vòng đời khác, có sự kiện timestamp-level được kiểm chứng, hoặc EDA cần phân tích phổ cho toàn bộ measurement.
## IMPORTANT — Chốt tiền xử lý FFT ban đầu cho XJTU-SY

**Quyết định:** Trong EDA FFT ban đầu của XJTU-SY, trừ giá trị trung bình của waveform rồi áp dụng cửa sổ Hann trước khi tính FFT thực một phía. Lưu đồng thời lưới tần số và phổ biên độ một phía, cùng với tần số trội, biên độ trội, tổng công suất phổ và bốn thống kê công suất theo dải tần cố định. Giữ độ dài waveform thực tế và tần số lấy mẫu trong từng dòng FFT.

**Ngày:** 2026-10-08

**Vấn đề được giải quyết:** Một thống kê FFT có thể tái lập cần quy định rõ cách xử lý giá trị trung bình, rò rỉ phổ, chuẩn hóa biên độ và waveform có độ dài thay đổi. Nếu để ngầm định, các lần so sánh sau sẽ khó tái lập.

**Trạng thái hệ thống hiện tại:** Mã EDA ghi một dòng thống kê miền thời gian cho mỗi Observation và 330 dòng FFT cho 15 trajectory × 2 kênh × 11 mốc. Waveform raw không bị sửa.

**Yêu cầu nghiệp vụ/dự án:** Làm cho lượt EDA đầu tiên có tính quyết định và truy vết được; giữ đủ thông tin phổ cho các biểu đồ và phân tích sau; chấp nhận waveform khác 32.768 mẫu.

**Các phương án đã cân nhắc:** FFT raw không trừ trung bình và không dùng cửa sổ; thêm mẫu 0 hoặc nội suy về độ dài cố định; chỉ lưu tần số trội; và tính phổ cho mọi measurement. Các phương án này bị hoãn hoặc loại vì để ngầm định rò rỉ/chuẩn hóa, tạo mẫu giả, làm mất thông tin hoặc tăng chi phí ban đầu không cần thiết.

**Lập luận:** Trừ trung bình loại thành phần DC không phải trọng tâm của so sánh rung. Cửa sổ Hann giảm rò rỉ trong khoảng thu hữu hạn. FFT thực một phía giữ phần tần số dương, còn việc lưu đầy đủ mảng tần số và biên độ giúp tái sử dụng output. Độ dài thực tế vẫn là nguồn sự thật, nên độ phân giải tần số được ghi theo từng dòng thay vì giả định cố định.

**Hệ quả:** Các output FFT có thể so sánh trực tiếp khi tần số lấy mẫu giống nhau, nhưng các waveform khác độ dài có độ phân giải tần số khác nhau và phải dùng lưới tần số đã lưu hoặc nội suy có ghi rõ khi vẽ. Output lớn hơn bản chỉ lưu vài số vô hướng. Mã ban đầu dùng các dải cố định 0–1 kHz, 1–5 kHz, 5–10 kHz và 10–12,8 kHz cho tần số lấy mẫu được tài liệu hóa là 25,6 kHz.

**Điều kiện xem xét lại:** Phương pháp phía sau yêu cầu chuẩn hóa biên độ, cửa sổ, detrend, ước lượng mật độ phổ, lưới tần số hoặc chuẩn hóa theo tần số lấy mẫu khác; hoặc dự án chuyển sang lưu phổ cho mọi measurement.
