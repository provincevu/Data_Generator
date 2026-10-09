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

## IMPORTANT — Chốt các thống kê miền thời gian XJTU-SY

**Quyết định:** Lưu std = sqrt(E[(x - mean)^2]), kurtosis Pearson raw E[(x - mean)^4] / std^4, và crest_factor = peak_abs / RMS cho mỗi Observation và mỗi kênh trong bảng thống kê EDA. Dùng moment theo toàn bộ mẫu trong một waveform; trả về kurtosis hoặc crest factor là NaN khi phương sai hoặc RMS bằng 0.

**Ngày:** 2026-10-08

**Vấn đề được giải quyết:** EDA cần định nghĩa rõ và tái lập được cho ba thống kê waveform sẽ được hiển thị trong animation lifecycle và dùng để so sánh.

**Lập luận:** Kurtosis được yêu cầu là moment trung tâm bậc bốn đã chuẩn hóa, không phải excess kurtosis của SciPy. Moment theo toàn bộ mẫu phù hợp với ký hiệu kỳ vọng và tránh âm thầm trừ 3 hoặc hiệu chỉnh mẫu. Crest factor thể hiện tính xung của tín hiệu so với RMS.

**Hệ quả:** Phải tạo lại xjtu_signal_summary.parquet sau khi thay đổi mã. Người dùng sau này không được hiểu kurtosis là excess kurtosis.

**Điều kiện xem xét lại:** Phân tích sau này yêu cầu ước lượng không chệch cho mẫu hoặc excess kurtosis; khi đó phải thêm trường có tên riêng thay vì âm thầm đổi nghĩa trường hiện tại.

## IMPORTANT — Cache các giai đoạn EDA XJTU-SY và dùng nhãn biểu đồ tiếng Việt

**Quyết định:** Pipeline EDA XJTU-SY lưu manifest cache tại xjtu_eda_cache.json. Pipeline cache độc lập bảng Parquet thống kê miền thời gian, bảng Parquet FFT và bảy ảnh tĩnh. Mỗi cache chỉ được dùng lại khi chữ ký file input và phiên bản/cấu hình của giai đoạn khớp; thay đổi một giai đoạn chỉ làm mất hiệu lực giai đoạn đó và các biểu đồ phía sau. Có tùy chọn buộc tính lại khi cần. Tiêu đề, trục, chú thích và ghi chú giải thích trên ảnh dùng tiếng Việt; tên định danh và tên metric chuẩn vẫn được giữ để dễ đối chiếu.

**Ngày:** 2026-10-09

**Vấn đề được giải quyết:** Chạy lại EDA sau mỗi thay đổi biểu đồ hoặc nhãn khiến pipeline đọc lại Parquet waveform 1,91 GB không cần thiết; nhãn chỉ bằng tiếng Anh cũng khó diễn giải.

**Trạng thái hệ thống hiện tại:** EDA có thống kê miền thời gian cho mọi Observation, FFT tại 11 mốc và các biểu đồ lifecycle/FFT/lifetime. Manifest cache ghi khóa theo chữ ký size/thời gian sửa đổi của input và phiên bản cấu hình từng giai đoạn.

**Yêu cầu nghiệp vụ/dự án:** Làm cho việc phát triển EDA lặp lại trên dữ liệu local thực tế nhanh hơn, không dùng âm thầm kết quả cũ, giải thích được ảnh bằng tiếng Việt và vẫn có cách buộc dựng lại toàn bộ.

**Các phương án đã cân nhắc:** Tính lại mọi giai đoạn mỗi lần chạy; chỉ cache báo cáo cuối; dùng một khóa chung cho mọi giai đoạn; hoặc chỉ cần thấy file tồn tại là dùng lại. Các phương án này lãng phí tài nguyên hoặc có nguy cơ dùng output cũ/dở dang.

**Lập luận:** Khóa theo từng giai đoạn cho phép thay đổi biểu đồ mà vẫn dùng lại hai bảng Parquet; thay đổi dữ liệu raw hoặc định nghĩa metric sẽ làm mới bảng miền thời gian và các giai đoạn sau. Chữ ký file rẻ hơn việc băm toàn bộ input 1,91 GB ở mỗi lần chạy; phiên bản/cấu hình giai đoạn cung cấp cơ chế vô hiệu hóa rõ ràng khi mã thay đổi. Nhãn tiếng Việt và ghi chú ngắn giúp đọc ảnh mà không phải tự dịch từng trục.

**Hệ quả:** Lần chạy đầu vẫn phải xử lý đầy đủ Parquet đầu vào. Nếu thay đổi cách tính, phải tăng phiên bản/cấu hình giai đoạn hoặc dùng tùy chọn buộc tính lại. Cache bị xóa hoặc không khớp sẽ khiến giai đoạn tương ứng chạy lại. Các ảnh vẫn được Git bỏ qua.

**Điều kiện xem xét lại:** Filesystem làm size hoặc thời gian sửa đổi không đáng tin cậy; cần hỗ trợ nhiều tiến trình EDA chạy đồng thời; hoặc cache phải di chuyển giữa nhiều máy, khi đó có thể cần băm nội dung và ghi fingerprint môi trường.

## IMPORTANT — Chốt schema feature Phase 3 và tiền xử lý không rò rỉ cho XJTU-SY

**Quyết định:** Định nghĩa schema feature phiên bản `xjtu_feature_v1` gồm 15 đặc trưng vô hướng cho mỗi kênh, theo thứ tự `mean`, `std`, `rms`, `peak_abs`, `peak_to_peak`, `kurtosis`, `crest_factor`, `dominant_frequency_hz`, `dominant_amplitude`, `total_spectral_power`, `spectral_entropy`, `band_power_0_1000_hz`, `band_power_1000_5000_hz`, `band_power_5000_10000_hz` và `band_power_10000_12800_hz`. Vector của mỗi snapshot vật lý nối đặc trưng horizontal trước rồi đến vertical, nên `D = 30`. Hợp đồng raw vẫn giữ một dòng cho mỗi kênh; bảng feature snapshot dẫn xuất có một dòng cho mỗi bearing × measurement và mang theo mask kênh hiện diện và mask feature hợp lệ.

Tính các đặc trưng phổ vô hướng cho mọi observation bằng chính sách đã chốt: trừ trung bình và dùng cửa sổ Hann. Spectral entropy là entropy Shannon đã chuẩn hóa của phổ công suất một phía sau cửa sổ. Không thêm STFT vào Phase 3.

Dùng split baseline theo nhóm, tất định cho tiền xử lý: condition 3 là test; `Bearing1_5` và `Bearing2_5` là validation; các bearing còn lại là train. Tính thống kê z-score theo từng feature chỉ từ các giá trị hữu hạn của bearing train. Giá trị thiếu hoặc không xác định được thay bằng mean của train trước khi chuẩn hóa và được đánh dấu bằng mask; không tự động cắt hay xóa outlier.

**Ngày:** 2026-10-09

**Vấn đề được giải quyết:** Dự án đã có EDA miền thời gian và FFT tại các anchor, nhưng chưa có vector feature cố định chiều cho mọi snapshot, chưa có spectral entropy và chưa có chuẩn hóa không rò rỉ hoặc báo cáo tự động về chất lượng feature trước khi mô hình hóa.

**Trạng thái hệ thống hiện tại:** Đã có observation raw XJTU-SY, metadata, thống kê miền thời gian và FFT tại 11 anchor. Pipeline feature mới tạo feature cho từng observation, bảng snapshot 30 chiều, scaler chỉ học từ train và báo cáo validation gồm giá trị không hữu hạn, feature hằng, outlier robust và tương quan cao.

**Yêu cầu nghiệp vụ/dự án:** Hoàn thành MVP feature-space dễ debug trước diffusion; giữ provenance của waveform raw; làm cho mọi snapshot so sánh được trong không gian cố định; ngăn phân phối validation/test ảnh hưởng preprocessing; giữ đủ mask và báo cáo để kiểm toán giá trị thiếu hoặc không xác định.

**Các phương án đã cân nhắc:**
1. Dùng mảng FFT có độ dài thay đổi làm input mô hình. Không chọn vì không xác định được `D` cố định khi độ dài waveform thay đổi.
2. Chỉ tính feature phổ tại 11 anchor EDA. Không chọn cho feature mô hình vì mô hình cần biểu diễn cho mọi snapshot.
3. Thêm STFT ngay. Tạm hoãn vì FFT và band feature hiện tại đủ cho MVP; quyết định dự án đã coi STFT là nâng cấp sau.
4. Fit chuẩn hóa trên toàn bộ trajectory. Không chọn vì làm rò rỉ phân phối validation/test.
5. Tự động xóa outlier hoặc feature tương quan cao. Không chọn vì giai đoạn validation đầu tiên cần báo cáo bằng chứng, không âm thầm thay đổi thông tin sinh từ raw.
6. Gộp hai kênh thành một Observation raw. Không chọn vì hợp đồng raw chuẩn phải giữ một dòng mỗi kênh; việc đóng gói hai kênh chỉ thuộc lớp snapshot dẫn xuất.

**Lập luận:** Mười lăm feature cho mỗi kênh bao phủ các thống kê miền thời gian đã chốt và phần tóm tắt phổ đầu tiên, đồng thời vẫn tất định và dễ kiểm toán. Nối hai kênh đã được tài liệu hóa tạo ra vector snapshot 30 chiều ổn định mà không thay đổi provenance raw. Split baseline giữ đúng yêu cầu tách theo bearing/condition và vẫn cho phép bổ sung các fold leave-one-condition-out xoay vòng sau này. Z-score chỉ học từ train đơn giản, tái lập được và không làm mất biên độ bằng clipping. Mask làm cho việc điền giá trị thiếu hoặc không xác định trở nên rõ ràng.

**Bằng chứng và giả định:** Tài liệu XJTU-SY ghi nhận hai kênh horizontal/vertical, tần số lấy mẫu 25,6 kHz và khoảng 32.768 mẫu mỗi measurement. Các quyết định trước đã chốt mean-centering, cửa sổ Hann, bốn dải tần, kurtosis Pearson raw và crest factor. Dữ liệu hiện tại có đủ hai kênh ở mọi measurement đã parse; hành vi mask được giữ cho các input thiếu trong tương lai.

**Hệ quả:** Phase 3 tạo `xjtu_observation_features.parquet`, `xjtu_snapshot_features.parquet`, `xjtu_feature_scaler.json`, `xjtu_feature_validation.json` và `xjtu_feature_report.json`. Bảng snapshot có `D = 30`; vector đã chuẩn hóa có thể đưa vào baseline hoặc prototype diffusion. STFT, encoder học được, chọn feature tự động và sửa outlier vẫn là việc tương lai. Việc gán train/validation/test này là quy ước preprocessing baseline, không phải bộ sinh fold đánh giá cuối cùng.

**Điều kiện xem xét lại:** Mô hình phía sau cần cách đóng gói kênh khác, có nhãn timestamp-level được kiểm chứng, có chế độ sampling khác, cần các fold đánh giá xoay vòng, cần họ chuẩn hóa khác hoặc có bằng chứng schema 15 feature/kênh bỏ sót thông tin suy giảm quan trọng. Mọi thay đổi phải tăng phiên bản schema feature và cập nhật cả hai decision record.

## IMPORTANT — Đặt yêu cầu bắt buộc để lifecycle phù hợp với dự đoán sức khỏe

**Quyết định:** Xem năm yêu cầu là tiêu chí bắt buộc để chấp nhận mọi lifecycle được sinh ra cho mô hình RUL, health index, phân loại giai đoạn thoái hóa hoặc dự đoán hỏng hóc: tiến trình khỏe mạnh/FPT/thoái hóa/EOL rõ ràng; biến đổi có ý nghĩa vật lý ở miền thời gian và tần số với xung tuần hoàn; nhãn sinh đồng bộ từ trạng thái tạo dữ liệu; biến thiên ngẫu nhiên có seed tái lập; và các kênh cảm biến đồng bộ với khác biệt tín hiệu theo hướng cảm biến.

**Ngày:** 2026-10-09

**Vấn đề được giải quyết:** Pipeline chỉ phóng đại biên độ của tín hiệu khỏe có thể tạo ra file nhìn có vẻ hợp lý nhưng khiến AI học mẹo như RMS. Cách này không tạo được chuyển tiếp có thể học, bằng chứng tần số lỗi có cơ sở vật lý, target đồng bộ, biến thiên thực tế hoặc hành vi đa kênh nhất quán.

**Trạng thái hệ thống hiện tại:** Dự án đã có observation raw XJTU-SY, metadata, EDA và trích xuất feature. Các yêu cầu lâu dài cho pipeline sinh lifecycle tổng hợp trước đây chưa được ghi thành chỉ dẫn bắt buộc. Lớp raw XJTU chuẩn vẫn phải dựa trên nguồn và không được nhầm với nhãn tổng hợp.

**Yêu cầu nghiệp vụ/dự án:** Sinh dữ liệu có thể dùng cho học có giám sát RUL hoặc giai đoạn thoái hóa; giữ nền khỏe mạnh; thể hiện FPT và EOL; có RUL và HI cho từng mẫu; tạo các kịch bản hỏng khác nhau nhưng tái lập được; và biểu diễn horizontal/vertical như các kênh của cùng một lifecycle vật lý.

**Các phương án đã cân nhắc:** Chấp nhận chỉ phóng đại biên độ; dùng một đường cong thoái hóa đơn điệu và tất định; sinh nhãn sau từ tên file; tạo các kênh cảm biến độc lập; hoặc chỉ thêm tần số lỗi như hiệu ứng trực quan mà không có cơ chế xung tuần hoàn. Không chọn vì các cách này khuyến khích học mẹo, che giấu chuyển trạng thái, làm lệch nhãn, vi phạm tính vật lý đa kênh hoặc không tạo được cấu trúc để học tần số lỗi.

**Lập luận:** Năm yêu cầu cùng nhau khống chế các lỗi quan trọng nhất của dữ liệu bảo trì dự đoán tổng hợp. Trạng thái sức khỏe ẩn dùng chung làm waveform và nhãn nhất quán; RUL đoạn thẳng theo FPT tạo target rõ ràng; xung tuần hoàn và tần số đặc trưng bổ sung cấu trúc ngoài biên độ; tuổi thọ và nhiễu ngẫu nhiên làm giảm ghi nhớ máy móc; đồng bộ thời gian giữa các kênh giữ được ý nghĩa vật lý của quan sát đa cảm biến. Seed và thông số sinh giúp tái lập và kiểm toán các lifecycle.

**Hệ quả:** Mọi pipeline sinh lifecycle sau này phải ghi FPT, EOL, stage, RUL, HI, seed và thông số sinh theo từng mẫu hoặc lifecycle. Pipeline phải cung cấp đủ thống kê miền thời gian/tần số để review chuyển tiếp và không được tuyên bố chính xác vật lý khi thiếu hình học hoặc hiệu chuẩn. Mọi ngoại lệ có chủ ý phải có decision record mới được review ở cả hai ngôn ngữ. Các yêu cầu này có thể làm pipeline phức tạp hơn và khiến kiểm tra bằng mắt đơn thuần không còn đủ.

**Điều kiện xem xét lại:** Nghiên cứu trên dữ liệu thật đã kiểm chứng cho thấy một yêu cầu không phù hợp với triển khai đích; một loại cảm biến khác cần hợp đồng đa kênh riêng; task đích là không giám sát và không dùng nhãn lifecycle; hoặc mô hình vật lý có thẩm quyền làm thay đổi cơ chế thoái hóa cần thiết. Khi đó phải giữ lại lý do cũ và version hóa thay đổi mới.

## IMPORTANT — Cho phép cấu hình các tần số đặc trưng của ổ bi XJTU-SY

**Quyết định:** Bổ sung `shaft_frequency_hz`, `bpfo_hz`, `bpfi_hz`, `bsf_hz` và `ftf_hz` vào bảng tóm tắt FFT XJTU-SY. Tính tần số trục từ `rotational_speed_rpm`. Chỉ tính BPFO, BPFI, BSF và FTF khi có tệp YAML đầy đủ thông số hình học ổ bi; nếu không thì để bốn giá trị này là null và ghi trạng thái `geometry_not_configured`. Không tự tạo thông số danh nghĩa cho model LDK UER204.

**Ngày:** 2026-10-09

**Vấn đề được giải quyết:** EDA miền tần số cần các tần số lỗi có ý nghĩa vật lý, nhưng context hiện có của dự án XJTU-SY chưa cung cấp bộ giá trị hình học đã được kiểm chứng gồm số con lăn, đường kính vòng chia, đường kính con lăn và góc tiếp xúc.

**Trạng thái hệ thống hiện tại:** Bảng FFT được tính tại 11 mốc vòng đời và đã lưu tần số lấy mẫu, lưới tần số, biên độ, tần số trội, tổng công suất phổ và công suất theo dải. EDA hiện nhận tùy chọn `--bearing-geometry` trỏ tới tệp YAML và lưu nguồn cùng trạng thái cấu hình trong từng dòng FFT và báo cáo EDA.

**Yêu cầu nghiệp vụ/dự án:** Cung cấp BPFO/BPFI/BSF/FTF cho phân tích lỗi về sau; giữ provenance; tránh độ chính xác giả; vẫn cho phép chạy các phần EDA khác trước khi có hình học xác thực; làm mất hiệu lực cache FFT và ảnh khi cấu hình này thay đổi.

**Các phương án đã cân nhắc:** Hard-code một bộ kích thước danh nghĩa của UER204; ước lượng hình học từ đỉnh waveform; bỏ qua toàn bộ tần số đặc trưng; hoặc bắt buộc phải có cấu hình. Không chọn hard-code và ước lượng vì có thể gắn diễn giải vật lý sai cho mọi output. Không bỏ tần số trục vì đây là đại lượng suy ra trực tiếp. Không bắt buộc cấu hình vì sẽ chặn các phần EDA không phụ thuộc vào hình học.

**Lập luận:** Công thức chuẩn dùng tần số trục `fr`, số con lăn `N`, đường kính con lăn `d`, đường kính vòng chia `D` và góc tiếp xúc `theta`: BPFO = `N/2 * fr * (1 - (d/D) cos(theta))`, BPFI = `N/2 * fr * (1 + (d/D) cos(theta))`, BSF = `D/(2d) * fr * (1 - ((d/D) cos(theta))^2)`, FTF = `1/2 * fr * (1 - (d/D) cos(theta))`. Tệp hình học bên ngoài làm cho giả định rõ ràng và có thể kiểm toán; thiếu hình học thì để null thay vì tạo số liệu giả.

**Hệ quả:** Schema FFT có thêm các cột tần số đặc trưng và trạng thái. Người dùng phải điền `configs/xjtu_bearing_geometry.example.yaml` từ nguồn kỹ thuật có thẩm quyền trước khi diễn giải BPFO/BPFI/BSF/FTF bằng số. Các lần chạy không truyền tùy chọn này vẫn hợp lệ cho các thống kê FFT khác, nhưng cần chạy lại để tạo schema mới.

**Điều kiện xem xét lại:** Có bản vẽ ổ bi XJTU-SY hoặc datasheet nhà sản xuất có thẩm quyền; tốc độ trục thay đổi trong một waveform và cần ước lượng tần số theo thời gian; xác nhận model ổ bi khác; hoặc dự án áp dụng mô hình hiệu chỉnh slip/hình học đã được kiểm chứng.

## IMPORTANT — Biểu diễn mỗi bearing XJTU-SY thành trajectory feature đầy đủ có độ dài thay đổi

**Quyết định:** Với Task 4.1, biểu diễn mỗi trajectory của bearing thành một sequence có thứ tự và độ dài thay đổi. Mỗi snapshot chứa vector feature Phase 3 `X_i ∈ R^30`, `elapsed_time_sec`, `measurement_index` nguồn và mask hợp lệ của feature. Dùng bảng Parquet dạng dài làm biểu diễn chuẩn, một dòng cho mỗi bearing × measurement snapshot. Chỉ tạo các mảng sequence đóng gói `[N_b, 30]`, mảng thời gian `[N_b]` và mask `[N_b, 30]` như artifact dẫn xuất cho huấn luyện; `N_b` thay đổi theo bearing.

Giữ `measurement_index` và `elapsed_time_sec` theo chronology nguồn. Measurement bị thiếu vẫn là khoảng trống thời gian thật, không renumber và không nội suy. Giữ `split` trong bảng như metadata provenance/đánh giá, nhưng không đưa vào `X_i`. Condition, bearing, fault, lifetime và metadata trajectory khác nằm ngoài vector feature mô hình; lifecycle fraction chỉ được dùng cho phân tích/đánh giá offline.

**Ngày:** 2026-10-09

**Vấn đề được giải quyết:** Phase 3 đã tạo feature cố định chiều cho từng snapshot, nhưng Task 4.1 cần biểu diễn trung thực toàn bộ lịch sử của bearing trước khi tạo window, anchor, target hoặc batch mô hình.

**Trạng thái hệ thống hiện tại:** Có 15 trajectory XJTU-SY và 9.216 snapshot với `D = 30`. Số measurement nguồn và elapsed time tuân theo quy ước chronology XJTU đã chốt. Bảng snapshot Phase 3 hiện là nền tảng dạng dài cho biểu diễn này.

**Yêu cầu nghiệp vụ/dự án:** Giữ toàn bộ trajectory và khoảng trống thời gian thật; hỗ trợ lifetime rất khác nhau giữa các bearing; làm cho biểu diễn dễ kiểm tra và tái lập; ngăn metadata lifecycle và split rò rỉ vào input mô hình; hỗ trợ các history window nhân quả và future target có độ dài thay đổi về sau.

**Các phương án đã cân nhắc:**
1. Làm phẳng toàn bộ bearing thành một vector cố định chiều. Không chọn vì độ dài trajectory khác nhau đáng kể và khó batch hiệu quả.
2. Resample hoặc nội suy mọi trajectory về cùng lưới thời gian. Không chọn vì tạo observation giả và che giấu measurement bị thiếu.
3. Chỉ dùng tensor đóng gói làm artifact chuẩn. Không chọn vì bảng dài dễ audit, lọc, join và tái lập hơn; tensor đóng gói vẫn hữu ích như artifact huấn luyện dẫn xuất.
4. Đưa condition, fault, lifetime hoặc split identifier vào `X_i`. Không chọn vì đây là metadata provenance/đánh giá và có thể làm rò rỉ cấu trúc thí nghiệm hoặc thông tin tương lai.

**Lập luận:** Sequence gồm các snapshot cố định chiều giữ đúng sự phân tách giữa biểu diễn từng snapshot và độ dài trajectory biến thiên. Bảng dài giữ chính xác identity và chronology nguồn, còn mảng dẫn xuất cung cấp dạng `[N_b, 30]` hiệu quả cho mã huấn luyện phía sau. Giữ mask và metadata riêng giúp hỗ trợ kênh thiếu và thí nghiệm không rò rỉ mà không thay đổi hợp đồng Observation raw.

**Bằng chứng và giả định:** Phase 3 đã chốt `D = 30` bằng cách nối 15 feature horizontal và 15 feature vertical. Các quyết định XJTU-SY yêu cầu giữ số measurement nguồn dạng số, coi measurement thiếu là khoảng trống thật, không nội suy waveform và loại lifecycle/failure information khỏi input inference baseline.

**Hệ quả:** Task 4.1 tạo bảng trajectory dạng dài làm nguồn chuẩn và có thể tạo artifact sequence theo từng bearing. Các task sau được phép tạo history window nhân quả, future target, padding mask và tensor batch từ biểu diễn này mà không đổi chronology. Phần lưu trữ và batching phải hỗ trợ `N_b` thay đổi; phải split toàn bộ trajectory trước khi tạo artifact dẫn xuất.

**Điều kiện xem xét lại:** Dataset mới cần atomic unit khác, một task cụ thể chứng minh cần lưới thời gian chung đã kiểm chứng, hoặc mô hình cần đóng gói multi-channel lossless mà format sequence dẫn xuất hiện tại không đáp ứng. Mọi thay đổi phải giữ bảng dài nguồn hoặc tạo một phiên bản thay thế có version.

## IMPORTANT — Lấy mẫu random anchor nhân quả tại snapshot XJTU-SY đã quan sát

**Quyết định:** Với Task 4.2, chỉ chọn `t_anchor` từ các snapshot hợp lệ đã quan sát, không chọn từ thời điểm liên tục nằm giữa hai measurement. Một anchor hợp lệ phải có ít nhất 10 snapshot hợp lệ, tính cả snapshot anchor, trong 1.800 giây trước anchor và phải có ít nhất một snapshot đã quan sát sau anchor. Tạo danh sách anchor hợp lệ riêng cho từng trajectory đầy đủ sau khi áp dụng split trajectory. Lấy mẫu bên trong từng bearing để trajectory dài không áp đảo phân phối anchor. Dùng seed tất định cho validation/test và chính sách tái lập `base_seed + epoch` cho train. Lưu `anchor_manifest.parquet` gồm identity trajectory, split, identity anchor, measurement index nguồn, elapsed time của anchor, số history/future và seed lấy mẫu.

Snapshot anchor thuộc history với `lag_sec = 0`. Các record history dùng `lag_sec = elapsed_time_sec - anchor_elapsed_time_sec`; measurement thiếu vẫn là khoảng trống thời gian thật, không nội suy và không renumber. Task 4.2 chỉ chọn anchor; việc tạo sequence history và future target thuộc task sau.

**Ngày:** 2026-10-10

**Vấn đề được giải quyết:** Biểu diễn trajectory đầy đủ cần một cách chọn điểm truy vấn nhân quả, tái lập được, không tạo timestamp giả, không để trajectory dài tạo quá nhiều anchor và không cho anchor vượt ranh giới split.

**Trạng thái hệ thống hiện tại:** Task 4.1 đã định nghĩa trajectory có độ dài thay đổi và snapshot cố định chiều. Snapshot XJTU-SY cách nhau xấp xỉ một phút nhưng có thể có measurement bị thiếu thật. Quy trình causal yêu cầu ít nhất 10 record trong 30 phút trước và chỉ dự đoán record sau anchor.

**Yêu cầu nghiệp vụ/dự án:** Giữ chronology không đều; tạo đủ điểm truy vấn random cho train; làm validation/test tái lập; cho mỗi bearing cơ hội đóng góp công bằng; bảo đảm mỗi anchor có history dùng được và future không rỗng; ngăn rò rỉ split và thông tin tương lai.

**Các phương án đã cân nhắc:**
1. Lấy mẫu thời điểm liên tục tùy ý. Không chọn vì anchor không tương ứng với snapshot feature đã quan sát và cần nội suy hoặc định nghĩa trạng thái hiện tại không rõ.
2. Lấy mẫu đều trên toàn bộ snapshot của dataset. Không chọn vì trajectory dài sẽ áp đảo phân phối train.
3. Chấp nhận anchor có dưới 10 record history. Không chọn vì protocol chính yêu cầu tối thiểu 10; context ngắn thuộc robustness evaluation riêng.
4. Chọn anchor trước khi áp dụng split trajectory. Không chọn vì khó audit leakage và có thể trộn artifact giữa các split.
5. Tạo history và target ngay trong bộ chọn anchor. Không chọn vì chọn anchor và tạo sample cần độc lập để dễ kiểm thử.

**Lập luận:** Anchor tại snapshot đã quan sát giữ đúng ngữ nghĩa thời gian nguồn và cung cấp trực tiếp `X_anchor`. Điều kiện và lấy mẫu theo bearing cân bằng 15 trajectory vật lý dù lifetime khác nhau rất lớn. Seed giúp validation/test tái lập, đồng thời vẫn tạo đa dạng cho train theo epoch. Yêu cầu có future record tránh target rỗng mà không đưa thông tin đó vào model input; việc kiểm tra future chỉ phục vụ tạo sample offline.

**Bằng chứng và giả định:** XJTU-SY ghi một CSV xấp xỉ mỗi phút, dự án định nghĩa `elapsed_time_sec` từ measurement nguồn dạng số, và quyết định causal cố định history tối đa 20 record trong 1.800 giây với tối thiểu 10 record cho protocol chính. Anchor không nhận lifecycle fraction, remaining life, failure time hoặc metadata trajectory làm input mô hình.

**Hệ quả:** Task 4.2 tạo manifest anchor tái lập được, chưa tạo window dùng trực tiếp cho mô hình. Trajectory dài không tự động đóng góp nhiều anchor hơn nếu ngân sách anchor theo bearing không cho phép. Các task sau phải dùng manifest để tạo history/future sequence, giữ measurement index nguồn và giữ mọi record dẫn xuất trong đúng split.

**Điều kiện xem xét lại:** Task sau cần query time tùy ý, có chính sách nội suy được kiểm chứng, protocol thay đổi minimum history hoặc đánh giá cần thiết kế lấy mẫu anchor khác. Mọi thay đổi phải tăng phiên bản schema manifest và chính sách lấy mẫu.

### Làm rõ — Điểm 1: context gần đây và target toàn bộ lifecycle còn lại

Cụm “dự đoán toàn bộ lifecycle” nghĩa là dự đoán toàn bộ trajectory còn lại sau `t_anchor`, không tái tạo các observation trước anchor. Vì vậy input context được giới hạn ở tối đa 20 snapshot thực tế gần `t_anchor` nhất trong `[t_anchor - 1800, t_anchor]`, có cả anchor và yêu cầu tối thiểu 10 record cho protocol chính. Giới hạn input này không giới hạn future target: task sau có thể cung cấp toàn bộ snapshot tương lai từ ngay sau anchor đến endpoint của trajectory hoặc `END_OF_TRAJECTORY`.

### Làm rõ — Điểm 2: phân phối số lượng context

Với protocol chính, lấy số nguyên `K ~ Uniform{10, ..., min(20, pool_size)}`. `K` bao gồm snapshot anchor. Anchor có dưới 10 record hợp lệ trong pool sẽ bị loại khỏi protocol chính. Với robustness protocol riêng, lấy `K ~ Uniform{3, ..., 9}` và gắn nhãn `context_regime = short_robustness`; các context ngắn này không được âm thầm trộn vào train hoặc kết quả tổng hợp của protocol chính.

**Lập luận:** `K` thay đổi thể hiện sự khác nhau thực tế về lượng history quan sát được nhưng vẫn giữ minimum-history của protocol chính. Phân phối đều rời rạc bao phủ công bằng từng kích thước context, cho phép đo độ nhạy theo `K` và tránh để context quá ngắn định nghĩa lại bài toán chính.
