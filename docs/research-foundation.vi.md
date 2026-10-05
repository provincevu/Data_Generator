# Nền tảng nghiên cứu: Sinh dữ liệu suy giảm ổ bi thưa và không đều

**Trạng thái:** nguồn sự thật chính thức của dự án  
**Phạm vi:** bộ sinh lỗi/suy giảm dự đoán, bắt đầu với XJTU-SY  
**Cập nhật hợp nhất lần cuối:** 2026-10-04

Tài liệu này ghi lại những quyết định nghiên cứu có tính lâu dài đã được thống nhất với chủ dự án. Mục đích của nó là để các công việc về sau không phụ thuộc vào lịch sử trò chuyện. Hãy cập nhật tài liệu khi một quyết định thay đổi; không được âm thầm thay thế hoặc bỏ qua các quyết định này trong code hay các thí nghiệm.

Tài liệu này không nhằm quy định mọi hành động bắt buộc phải tuân theo. Mục đích của nó là giúp chúng ta có một cách hiểu rõ ràng về việc chúng ta đang làm gì, tại sao chúng ta làm như vậy và những quyết định nào đã được đưa ra. Nếu có bất kỳ điều gì trong tài liệu này trở nên không hợp lý, lỗi thời hoặc không còn phù hợp với dự án, chúng ta hoàn toàn có thể và nên cùng nhau thảo luận để thống nhất thay đổi. Không được tự ý âm thầm chỉnh sửa hoặc ghi đè nội dung của tài liệu này mà không thảo luận.

Mục tiêu là làm điều tốt nhất cho dự án thay vì máy móc tuân theo những luật lệ hoặc ràng buộc cứng nhắc. Những quyết định này nên được xem là hướng dẫn và bối cảnh chung, không phải những giới hạn bất biến. Hãy sử dụng phán đoán hợp lý về mặt kỹ thuật và nghiên cứu khi hoàn cảnh yêu cầu, đồng thời cập nhật tài liệu khi một quyết định quan trọng thực sự thay đổi.

## Phát biểu bài toán trong một câu

Từ lịch sử quan sát thưa và không đều, suy ra trạng thái suy giảm hiện tại của ổ bi, sau đó sinh một phân phối các quỹ đạo suy giảm tương lai có khả năng xảy ra tại những thời điểm tương đối bất kỳ trong tương lai.

\[
\boxed{
\text{lịch sử thưa, không đều}
\rightarrow
\text{trạng thái suy giảm hiện tại}
\rightarrow
\text{các quỹ đạo suy giảm tương lai}
}
\]

Với lịch sử $H_t$ và các truy vấn $Q$, mục tiêu là:

\[
P(X_{future}\mid H_t,Q)
\]

trong đó

\[
H_t=\{(X_i,\Delta t_i,C_i)\}_{i=1}^{K},
\qquad
Q=\{\Delta t_{f1},\ldots,\Delta t_{fn}\}.
\]

`X_i` là véc-tơ đặc trưng được trích xuất từ cảm biến, `Δt_i` là thời gian tương đối so với mốc hiện tại (bằng `0` tại thời điểm hiện tại), và `C_i` là ngữ cảnh vận hành vật lý. Đầu ra là nhiều quỹ đạo tương lai, không phải một dự báo tất định duy nhất hay một mẫu hỏng hóc duy nhất.

## Các quyết định không được thỏa hiệp

1. **Đầu vào suy luận không bao gồm tỷ lệ vòng đời / phần trăm tuổi thọ.** $\tau=t/T_{failure}$ là siêu dữ liệu ngoại tuyến, chỉ dùng cho phân tích, lấy mẫu, đánh giá hoặc giám sát phụ tùy chọn. Mô hình khi triển khai phải học trạng thái hiện tại từ lịch sử.
2. **Đầu vào thời gian là thời gian tương đối, không phải tuổi tuyệt đối của ổ bi.** Hệ thống giám sát có thể bắt đầu theo dõi một ổ bi khi nó đã hoạt động được một thời gian, do đó tuổi tuyệt đối trong huấn luyện không tương thích về ngữ nghĩa với lúc suy luận. Dùng thời gian tương đối so với mốc truy vấn cho cả lịch sử lẫn các truy vấn tương lai.
3. **Điều kiện vận hành là ngữ cảnh vật lý, không dùng mã điều kiện làm đặc trưng chính.** Với XJTU-SY, dùng `[rotation_speed_hz, radial_load_kn]`; các môi trường sau này có thể dùng RPM, tải, mô-men xoắn, nhiệt độ, áp suất và những đại lượng vật lý liên quan.
4. **Bắt đầu trong không gian đặc trưng, không dùng khuếch tán dạng sóng thô.** MVP xử lý từng ảnh chụp rung động thành khoảng 32–128 đặc trưng thống kê/phổ có thể diễn giải. Dạng sóng thô / STFT / CWT / bộ mã hóa học được là các nâng cấp về sau.
5. **Chia tập đánh giá theo ổ bi (tài sản), tuyệt đối không chia ngẫu nhiên theo hàng dữ liệu.** Quỹ đạo của một ổ bi không được xuất hiện đồng thời trong tập huấn luyện và tập kiểm thử giữ lại.
6. **Trước khi làm việc với nhiều tập dữ liệu, hãy dùng các điều kiện vận hành XJTU-SY làm miền có kiểm soát.** Thiết lập khả năng thích nghi C1+C2 → C3 trước khi thử IMS/NASA hoặc dữ liệu nhà máy.
7. **Xây dựng mô hình cơ sở và đánh giá trước khi làm khuếch tán có điều kiện.** Khuếch tán phải chứng minh được lợi ích so với phép duy trì trạng thái và các mô hình cơ sở thời gian không đều.
8. **“Bình thường” là khái niệm vận hành, không phải bằng chứng về trạng thái nguyên sơ về mặt vật lý.** Với XJTU, các đoạn đầu vòng đời/tham chiếu chỉ là đại diện gần đúng; không được khẳng định phép đo đầu tiên là một ổ bi hoàn toàn mới nếu dữ liệu không chứng minh điều đó.

## Các giả thuyết nghiên cứu

- **H1 — Học suy giảm theo thời gian:** lịch sử không đều có thể dự báo/sinh ra suy giảm tương lai trong cùng một miền.
- **H2 — Khả năng chống chịu khi dữ liệu thưa:** phương pháp vẫn hữu ích khi loại bỏ rất nhiều quan sát (kể cả loại bỏ đến 99%) và lấy mẫu không đều.
- **H3 — Thích nghi giữa các miền có kiểm soát:** mô hình huấn luyện trên XJTU C1+C2 có thể thích nghi sang C3 với nhiều quan sát bình thường ở miền đích và rất ít quan sát suy giảm ở miền đích.

Chỉ nên ưu tiên các tập dữ liệu khác sau khi H1–H3 được củng cố bằng bằng chứng.

## Thiết lập XJTU-SY ban đầu

- 15 ổ bi được chạy đến hỏng, phân bố trên ba điều kiện vận hành:
  - C1: 35 Hz / 12 kN
  - C2: 37.5 Hz / 11 kN
  - C3: 40 Hz / 10 kN
- Dữ liệu rung có hai kênh, được lấy mẫu ở 25.6 kHz trong các ảnh chụp dài 1.28 giây (32,768 mẫu mỗi ảnh chụp), thu thập định kỳ.
- Dùng véc-tơ điều kiện `[f_rot, load]`, không chỉ dùng nhãn `1`, `2` và `3`.

## Định hướng kiến trúc

```text
dạng sóng rung thô
  → quy trình tín hiệu/đặc trưng
  → véc-tơ đặc trưng X + thời gian tương đối Δt + ngữ cảnh vận hành C
  → bộ mã hóa quan sát
  → bộ mã hóa lịch sử không đều (trạng thái hiện tại z_t)
  → khuếch tán trong không gian đặc trưng có điều kiện theo z_t, C và các truy vấn Δt tương lai
  → quỹ đạo đặc trưng tương lai / các bản tóm tắt phân phối
```

### Các mô-đun cốt lõi và thứ tự ưu tiên

| Mô-đun | Trách nhiệm | Ưu tiên |
| --- | --- | --- |
| Bộ chuyển đổi tập dữ liệu | dữ liệu thô → lược đồ quan sát chung | P0 |
| Quy trình tín hiệu | dạng sóng → đặc trưng thống kê/phổ tất định | P0 |
| Bộ tạo lịch sử không đều | mốc ngẫu nhiên, lịch sử thưa/không đều, truy vấn tương lai | P0 |
| Bộ mã hóa quan sát | véc-tơ đặc trưng → embedding | P0 |
| Bộ mã hóa điều kiện | ngữ cảnh vật lý → embedding | P1 |
| Bộ mã hóa lịch sử | Transformer nhận biết thời gian làm mô hình chính; GRU-D / Neural CDE làm mô hình cơ sở | P1 |
| Bộ sinh suy giảm | khuếch tán có điều kiện trên quỹ đạo đặc trưng tương lai | P1 |
| Bộ thích nghi miền | đóng băng mô hình tổng quát; khớp bộ thích nghi nhẹ ở miền đích | P2 |
| Đánh giá | điểm, phân phối, phổ, quỹ đạo, kiểm thử tác vụ phía sau | P0 cùng với mô hình |

### Các biểu diễn ứng viên

Các đặc trưng ban đầu gồm RMS, độ lệch chuẩn, kurtosis, độ lệch (skewness), giá trị đỉnh, hệ số đỉnh (crest factor), đỉnh-đỉnh, năng lượng dải, entropy phổ và các đặc trưng liên quan. Mọi phép biến đổi phải mang tính tất định. Chỉ khớp phép chuẩn hóa trên các ổ bi huấn luyện, sau đó áp dụng cho tập xác thực/kiểm thử.

## Hợp đồng dữ liệu

### Quan sát

```text
Observation {
  asset_id,
  timestamp,
  features[D],
  condition[C]
}
```

Siêu dữ liệu tập dữ liệu còn mang `condition_id`, tốc độ quay, tải hướng kính, chỉ số phép đo, thời gian đã trôi qua, thời điểm hỏng, tỷ lệ vòng đời và loại lỗi nếu có.

### Tác vụ quỹ đạo

```text
TrajectoryTask {
  history: [{features, relative_time, condition}, ...],
  future_queries: [positive relative times],
  future_targets: [feature vectors aligned with queries]
}
```

Khung mã ban đầu gồm ba đối tượng: `Trajectory`, `TrajectoryTask` và `ModelPrediction`.

### Quy tắc lấy mẫu

- Chọn ngẫu nhiên một mốc thời gian thay vì chỉ dự báo từ đầu vòng đời.
- Ngẫu nhiên hóa kích thước lịch sử, vị trí các điểm trong lịch sử, khoảng cách giữa các điểm, mật độ và chân trời dự báo.
- Chuyển mỗi dấu thời gian trong lịch sử thành `timestamp - anchor`; mốc neo có giá trị bằng không.
- Truy vấn các thời điểm tương đối dương bất kỳ, không đều và về sau có thể liên tục.
- Mô phỏng mật độ ở mức 100%, 50%, 20%, 10%, 5% và 1%.
- So sánh cách lấy mẫu đều, ngẫu nhiên không đều và tập trung thành cụm không đều.

## Quy trình thực nghiệm

### Đánh giá trong miền

- Giữ lại toàn bộ ổ bi cho tập xác thực và kiểm thử.
- Đánh giá với lịch sử dày, thưa, không đều và có chân trời dự báo thay đổi.
- Các mô hình cơ sở theo thứ tự: duy trì trạng thái (`X_future = X_current`), xu hướng tuyến tính không đều, GRU-D, Transformer nhận biết thời gian, Neural CDE tùy chọn.
- Đánh giá các độ đo điểm (MAE, RMSE, tương quan), độ đo phân phối (ví dụ MMD và cấu trúc tương quan), độ đo phổ (PSD/FFT/năng lượng dải), độ đo quỹ đạo (DTW, tương quan quỹ đạo, tính đơn điệu HI) và một tác vụ thực tế phía sau.
- So sánh tác vụ phía sau: huấn luyện chỉ bằng dữ liệu thật, chỉ bằng dữ liệu tổng hợp, và bằng dữ liệu thật kết hợp tổng hợp; luôn kiểm thử trên các ổ bi thật chưa thấy.

### Mục tiêu chấp nhận cho MVP nghiên cứu

1. Có thể tái lập quy trình từ dữ liệu XJTU thô → quan sát đã xử lý → tập dữ liệu tác vụ.
2. Lấy mẫu tác vụ thưa/không đều hoạt động với nhiều kiểu lấy mẫu.
3. Bộ sinh tạo ra các quỹ đạo tương lai, không chỉ một điểm hay một lớp hỏng hóc.
4. Mô hình vượt mô hình duy trì trạng thái trên phần lớn các chân trời dự báo thực được giữ lại.
5. Mô hình vẫn hữu ích khi quan sát thưa và không đều.
6. C1+C2 có thể thích nghi sang C3 với ít mẫu suy giảm.
7. Chất lượng tăng có hệ thống khi số mẫu suy giảm ở miền đích tăng từ 0 → 1 → 3 → 5 → 10.

Mức cải thiện thường được nhắc đến là +5% khi kết hợp dữ liệu thật và tổng hợp chỉ là mục tiêu kỹ thuật, không phải ngưỡng khoa học phổ quát.

## Thích nghi giữa các miền có kiểm soát

Chuẩn đối sánh chính hướng tới nhà máy:

```text
nguồn: C1 + C2
đích: C3
thích nghi: nhiều quan sát bình thường ở miền đích + 0/1/3/5/10/nhiều hơn các quan sát suy giảm ở miền đích
test: các ổ bi đích được giữ lại, không nằm trong tập hỗ trợ có giám sát
```

Huấn luyện một mô hình tổng quát, đóng băng mô hình đó và khớp một bộ thích nghi nhẹ thay vì tinh chỉnh toàn bộ mô hình bằng một vài mẫu đích.

Thực hiện các hoán vị nguồn-đích: C1+C2 → C3, C1+C3 → C2, C2+C3 → C1.

Cần phân biệt hai quy trình thích nghi hợp lệ:

- **Quy nạp (inductive):** chỉ thấy các quan sát bình thường/lỗi ở miền đích của những ổ bi thuộc tập hỗ trợ trong lúc thích nghi; các ổ bi kiểm thử hoàn toàn chưa được thấy.
- **Truyền nạp (transductive, quy trình chính hướng tới nhà máy):** có thể dùng các quan sát bình thường từ máy kiểm thử, trong khi nhãn suy giảm chỉ được dùng làm tập hỗ trợ few-shot.

## Mô phỏng gần với nhà máy

Trước khi triển khai thực tế tại nhà máy, hãy giảm mật độ và ngẫu nhiên hóa quỹ đạo XJTU định kỳ thành một lịch quan sát thưa giống lịch theo ngày/giờ. Toàn bộ quỹ đạo là dữ liệu chuẩn; các điểm được quan sát tạo thành lịch sử, còn các điểm tương lai bị ẩn tạo thành tập kiểm thử. Đối sánh ở mật độ quan sát 1%, 5%, 10% và 20%. Việc này xác định liệu hệ thống có hoạt động trong kịch bản giám sát thưa dự kiến hay không.

## Lộ trình và thứ tự phụ thuộc

```text
1. Phát biểu bài toán + hợp đồng dữ liệu + quy trình thực nghiệm
2. Môi trường có thể tái lập và quản lý phiên bản tập dữ liệu
3. Nạp/phân tích XJTU và siêu dữ liệu
4. Trích xuất tín hiệu/đặc trưng và chuẩn hóa chỉ dựa trên tập huấn luyện
5. Đối tượng quỹ đạo đầy đủ + bộ lấy mẫu tác vụ thưa/không đều ngẫu nhiên
6. Mô hình cơ sở duy trì trạng thái và tuyến tính
7. Mô hình cơ sở Transformer nhận biết thời gian (GRU-D/CDE tùy chọn)
8. Khung đánh giá và kiểm thử trên các ổ bi chưa thấy
9. Khuếch tán có điều kiện trong không gian đặc trưng và lấy mẫu nhiều quỹ đạo
10. Đánh giá trong miền với dữ liệu thưa/không đều
11. Bộ thích nghi đích C1+C2 → C3 và đường cong few-shot
12. Phân tích loại bỏ thành phần và mô phỏng gần với nhà máy
13. Phục vụ/đăng ký mô hình chỉ sau khi mô hình ổn định
```

Không bắt đầu Transformer hoặc khuếch tán trước khi hoàn tất bộ nạp dữ liệu, quy trình đặc trưng, quỹ đạo/bộ lấy mẫu và các mô hình cơ sở đơn giản.

## Hợp đồng phục vụ trong tương lai (không thuộc MVP)

`POST /v1/generate` cần nhận các quan sát, thời gian tương đối, điều kiện, truy vấn tương lai và `num_samples`; trả về các quỹ đạo được sinh, bản tóm tắt P10/P50/P90 hoặc trung bình/trung vị, độ bất định và siêu dữ liệu phiên bản. Quy trình suy luận tải mô hình một lần lúc khởi động: quan sát thô → đặc trưng → bộ tạo thời gian tương đối → bộ mã hóa lịch sử → bộ lấy mẫu khuếch tán → giải mã/xử lý hậu kỳ.

Mỗi mô hình được đăng ký phải gắn với `model_version`, `dataset_version`, `feature_schema_version`, `config_version`, `git_commit` và `training_seed`.

## Ưu tiên công nghệ

- Python 3.11; PyTorch; NumPy; SciPy; pandas; PyArrow; scikit-learn.
- Hydra/OmegaConf/Pydantic cho cấu hình và hợp đồng dữ liệu.
- Parquet cùng Zarr/HDF5 khi cần; DVC để quản lý phiên bản tập dữ liệu/quy trình; MLflow cho các lần chạy và dòng dõi/đăng ký mô hình.
- pytest, ruff và mypy; Matplotlib/Plotly để phân tích.
- FastAPI/Uvicorn/Docker chỉ sau khi nghiên cứu được kiểm chứng.
- GPU 8 GB (ví dụ GTX 1070) phù hợp cho nguyên mẫu nhỏ trong không gian đặc trưng khi dùng mixed precision và tích lũy gradient; đây không phải lý do để chọn khuếch tán dạng sóng thô.

## Nhật ký quyết định

| Ngày | Quyết định | Lý do |
| --- | --- | --- |
| 2026-10-04 | Dùng cách đặt bài toán lịch sử thưa, không đều → trạng thái hiện tại → quỹ đạo tương lai. | Phù hợp với thực tế quan sát khi triển khai. |
| 2026-10-04 | Loại tỷ lệ vòng đời khỏi đầu vào suy luận chính. | Ngăn rò rỉ thông tin vòng đời và giúp suy luận khả thi khi không có thời điểm hỏng. |
| 2026-10-04 | Dùng thời gian tương đối làm tín hiệu thời gian chính. | Tránh sai khác ngữ nghĩa giữa huấn luyện và suy luận về tuổi quan sát. |
| 2026-10-04 | Xem điều kiện XJTU là các miền có kiểm soát trước khi dùng tập dữ liệu bên ngoài. | Cho phép thu thập bằng chứng thích nghi có kiểm soát và đáng tin cậy. |
| 2026-10-04 | Bắt đầu với sinh dữ liệu trong không gian đặc trưng. | Giúp MVP dễ gỡ lỗi và phù hợp với năng lực tính toán hiện có. |
