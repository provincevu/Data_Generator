# Các yêu cầu cốt lõi khi sinh dữ liệu lifecycle

**Trạng thái:** yêu cầu bắt buộc của dự án. Phải đọc tài liệu này trước khi triển khai, sửa, kiểm thử hoặc diễn giải bất kỳ công việc nào liên quan đến sinh dữ liệu lifecycle, tín hiệu rung tổng hợp, RUL, chỉ số sức khỏe, giai đoạn thoái hóa hoặc dự đoán hỏng hóc.

Một pipeline không được xem là hoàn chỉnh chỉ vì nó sinh ra được waveform. Dữ liệu phải thể hiện được tiến trình thoái hóa có ý nghĩa cho mô hình AI có giám sát.

## 1. Tiến trình trạng thái sức khỏe rõ ràng

Mỗi lifecycle phải có giai đoạn khỏe mạnh, điểm chớm thoái hóa FPT, giai đoạn thoái hóa và điểm hỏng hoàn toàn EOL. Giai đoạn khỏe mạnh phải chứa nhiễu nền cơ khí ổn định, không chứa xu hướng thoái hóa ẩn. Chuyển tiếp tại FPT phải tự nhiên, liên tục và có ý nghĩa vật lý, không phải một bước nhảy biên độ đột ngột. FPT và EOL phải được lưu trong metadata và truy ra được cho mọi mẫu sinh ra.

## 2. Biến đổi có ý nghĩa vật lý ở miền thời gian và tần số

Không được tạo thoái hóa bằng cách chỉ nhân waveform khỏe mạnh với biên độ tăng dần. Pipeline phải thay đổi cấu trúc tín hiệu ở cả hai miền:

- Thống kê miền thời gian phải biến đổi phi tuyến. RMS và peak có thể tăng theo quy luật phi tuyến; kurtosis thường tăng khi xung va đập bắt đầu được phát hiện, sau đó có thể giảm nhẹ hoặc chững lại khi hư hỏng lan rộng. Đường cong cụ thể phải cấu hình được và có thể kiểm toán.
- Miền tần số phải có thành phần lỗi có cơ sở vật lý: BPFO, BPFI, BSF hoặc FTF khi biết hình học ổ bi và tốc độ quay, cùng các dải phụ liên quan đến tần số trục khi phù hợp. Phải bơm chuỗi xung va đập tuần hoàn và đáp ứng cộng hưởng vào nền khỏe; năng lượng tại tần số đặc trưng phải tăng dần theo thoái hóa.
- Nếu thiếu hình học hoặc thông số hiệu chuẩn, output phải ghi rõ trạng thái thiếu dữ liệu; không được âm thầm tự tạo tần số vật lý.

## 3. Tự động đồng bộ nhãn huấn luyện

Mỗi mẫu sinh ra phải nhận nhãn từ chính trạng thái lifecycle dùng để sinh waveform:

- RUL chuẩn hóa dạng đoạn thẳng giữ `1.0` trong toàn bộ giai đoạn khỏe mạnh và giảm tuyến tính từ `1.0` tại FPT xuống `0.0` tại EOL.
- Health Index (HI) là chuỗi liên tục, bắt đầu ở `1.0` và giảm dần về `0.0` khi hư hỏng tiến triển.
- Tối thiểu phải lưu lifecycle ID, chỉ số/thời điểm mẫu, FPT, EOL, giai đoạn sức khỏe, RUL và HI. Nhãn phải sinh từ một nguồn sự thật chung, không được dựng lại về sau chỉ từ tên file.

## 4. Đa dạng ngẫu nhiên và trồi sụt

Các lifecycle khác nhau không được là bản sao giống hệt nhau. Tuổi thọ và, khi phù hợp, FPT phải biến thiên theo phân phối Weibull, log-normal hoặc phân phối tương đương có tài liệu hóa. Tốc độ thoái hóa, cường độ xung, cộng hưởng, nhiễu tải/môi trường và nhiễu quan sát phải thay đổi giữa các lifecycle. Đường cong đo được được phép dao động hoặc hồi phục tạm thời; không bắt buộc đơn điệu tuyệt đối. Mỗi lifecycle phải lưu random seed và thông số sinh để có thể tái lập.

## 5. Tính nhất quán đa kênh cảm biến

Kênh ngang và kênh đứng phải dùng chung đồng hồ lifecycle, FPT, EOL và quỹ đạo sức khỏe ẩn. Năng lượng, pha, cộng hưởng, nhiễu và khả năng nhìn thấy xung có thể khác nhau theo hướng cảm biến và tải. Biểu diễn sinh ra phải hỗ trợ dạng đầu vào `(time_steps, channels)` và không được tạo nhãn sức khỏe mâu thuẫn giữa các kênh tại cùng một thời điểm vật lý.

## Câu hỏi bắt buộc khi review

Trước khi chấp nhận thay đổi pipeline, phải kiểm tra thay đổi đó còn giữ đủ cả năm yêu cầu, đồng bộ FPT/EOL với nhãn, giữ provenance của các giả định vật lý và lưu seed/cấu hình. Mọi ngoại lệ có chủ ý phải được ghi thành decision record trong `docs/decisions.md` và `docs/decisions_vi.md`.
