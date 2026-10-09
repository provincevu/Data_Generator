# Hướng dẫn dự án

### **Ghi nhận các quyết định lâu dài**

Ghi lại các quyết định quan trọng của dự án để lý do và bối cảnh của chúng vẫn có thể được hiểu độc lập với lịch sử trò chuyện.

- Ghi lại các quyết định khi chúng được đưa ra, đặc biệt là những quyết định mà người dùng đã tham gia sâu hoặc đưa ra định hướng đáng kể. Những quyết định này nên được đánh dấu rõ ràng là **important**.
- Mỗi bản ghi quyết định nên bao gồm:
  - **Quyết định:** mô tả ngắn gọn nội dung đã được quyết định.
  - **Thời gian:** thời điểm quyết định được đưa ra.
  - **Vấn đề được giải quyết:** vấn đề hoặc câu hỏi dẫn đến quyết định này.
  - **Trạng thái hệ thống hiện tại:** trạng thái liên quan của hệ thống tại thời điểm đưa ra quyết định.
  - **Yêu cầu nghiệp vụ:** các yêu cầu nghiệp vụ hoặc yêu cầu của dự án đứng phía sau quyết định.
  - **Các phương án đã cân nhắc:** những phương án đáng kể đã được xem xét.
  - **Lập luận:** tại sao phương án này được lựa chọn, bao gồm:
    - các tiêu chí được sử dụng để đánh giá các phương án;
    - lập luận và lý do hỗ trợ cho quyết định;
    - các giả định làm cơ sở cho quyết định;
    - bằng chứng hỗ trợ cho các lập luận và giả định đó.
  - **Hệ quả:** các hệ quả tích cực và tiêu cực được dự kiến từ quyết định.
  - **Điều kiện xem xét lại:** những điều kiện hoặc hoàn cảnh mà khi đó quyết định có thể không còn phù hợp và cần được xem xét lại.
- Không chỉ ghi lại kết luận của một quyết định. Hãy lưu đủ bối cảnh để có thể hiểu được **tại sao** quyết định được đưa ra và **khi nào** quyết định đó cần được xem xét lại.
- Khi một quyết định thay đổi, hãy cập nhật bản ghi của quyết định đó thay vì âm thầm thay thế nó ở nơi khác trong code, thí nghiệm hoặc tài liệu.
- Nếu một quyết định có vẻ không hợp lý, đã lỗi thời hoặc không còn phù hợp với nhu cầu hiện tại của dự án, hãy thảo luận và xem xét lại trước khi thay đổi bản ghi quyết định lâu dài.
- Ghi lại các quyết định của dự án vào `docs/decisions.md`.
- Trước khi thực hiện một hành động có thể bị ảnh hưởng bởi các quyết định trước đó, hãy xem lại các mục liên quan trong `docs/decisions.md`. Đảm bảo rằng hành động dự kiến không vô tình xung đột với các quyết định đã được đưa ra trước đây.
- Đồng thời hãy cập nhật cả vào trong `docs/decisions_vi.md` để tôi có thể đọc một cách dễ dàng.
- Nếu hành động dự kiến có vẻ xung đột với một quyết định hiện có, không được âm thầm ghi đè quyết định trước đó. Hãy xem xét sự xung đột, thảo luận xem quyết định đó có cần thay đổi hay không, cập nhật cả `docs/decisions.md` và `docs/decisions_vi.md` khi quyết định được chính thức sửa đổi.


### **Các yêu cầu khi trả lời**
- Khi trả lời tôi, hạn chế sử dụng các thuật ngữ tiếng anh gây khó hiểu (vẫn có thể sử dụng các thuật ngữ tiếng anh nếu việc dịch sang tiếng việt trở nên không sát nghĩa). Đối với tôi, một cuộc hội thoại tốt là cuộc hội thoại mà cả 2 bên đều hiểu ý của nhau

### **Yêu cầu bắt buộc khi sinh dữ liệu lifecycle**

Trước khi thực hiện bất kỳ hành động nào để triển khai, sửa, kiểm thử, review hoặc diễn giải pipeline sinh dữ liệu lifecycle, tín hiệu rung tổng hợp, RUL, chỉ số sức khỏe, các giai đoạn thoái hóa hoặc nhãn dự đoán hỏng hóc, Agent bắt buộc phải đọc:

- `docs/lifecycle_generation_requirements.md`
- `docs/lifecycle_generation_requirements_vi.md`
- các mục liên quan trong `docs/decisions.md` và `docs/decisions_vi.md`

Đây là yêu cầu bắt buộc, không phải gợi ý. Agent phải kiểm tra đủ cả năm yêu cầu: tiến trình khỏe mạnh/FPT/thoái hóa/EOL rõ ràng; biến đổi miền thời gian và tần số có ý nghĩa vật lý với xung tuần hoàn; nhãn RUL/HI đồng bộ; đa dạng ngẫu nhiên có seed tái lập; và tính nhất quán giữa các kênh cảm biến. Nếu thay đổi cố ý vi phạm một yêu cầu, phải dừng để ghi nhận hoặc xem xét một quyết định rõ ràng trong cả hai file quyết định trước khi tiếp tục.
### **Hướng dẫn và context lâu dài về dataset XJTU-SY**

Trước khi thực hiện bất kỳ task nào đọc, biến đổi, gán nhãn, phân tích, chia tập hoặc xây dựng model trên dữ liệu XJTU-SY, Agent bắt buộc phải đọc:

- `data/raw/XJTU-SY_Bearing_Datasets/Data/XJTU-SY_Bearing_Datasets/Introduction_to_XJTU-SY_Bearing_Dataset.pdf`
- các mục liên quan trong `docs/decisions.md` và `docs/decisions_vi.md`

PDF là nguồn của các sự thật về dataset. Các giá trị đầy đủ từ Bảng 2 được lưu trong `docs/xjtu_dataset_reference_vi.md`; hãy đọc tài liệu này trước khi triển khai metadata XJTU. PDF là bằng chứng và tài liệu mô tả, không thay thế cho các quyết định của dự án. Nếu một quyết định của dự án khác với một giả định đơn giản hóa trong PDF, phải tuân theo quyết định của dự án và giữ rõ sự khác biệt đó trong tài liệu.

Các thông tin quan trọng từ PDF:

- XJTU-SY có 15 bearing với trajectory hoàn chỉnh từ lúc bình thường đến failure.
- Có 3 điều kiện vận hành, mỗi condition có 5 bearing:
  - condition 1: 2100 rpm (35 Hz), 12 kN;
  - condition 2: 2250 rpm (37.5 Hz), 11 kN;
  - condition 3: 2400 rpm (40 Hz), 10 kN.
- Model bearing được thử nghiệm là LDK UER204.
- Có hai accelerometer PCB 352C33 đặt lệch nhau 90 độ, tạo ra hai channel horizontal và vertical.
- Tần số lấy mẫu được tài liệu hóa là 25,6 kHz. Mỗi lần ghi có 32.768 mẫu (1,28 giây), lặp lại mỗi 1 phút.
- Mỗi lần sampling được lưu thành một CSV; cột đầu là tín hiệu rung horizontal và cột thứ hai là tín hiệu rung vertical.
- Bảng 2 cung cấp số CSV, lifetime được công bố và fault element cho từng bearing.
- Tài liệu mô tả thí nghiệm tiếp tục cho đến khi biên độ cực đại của horizontal hoặc vertical vượt 10 * A_h, trong đó A_h là biên độ cực đại ở giai đoạn vận hành bình thường.
- PDF phân biệt fault element trong Bảng 2 với dạng hỏng thể hiện qua hình ảnh như inner-race wear, cage fracture, outer-race wear và outer-race fracture.

Các quy ước của dự án cũng phải được giữ nguyên:

- Tên file số `n.csv` là measurement nguồn thứ `n`; không đánh lại measurement sau khi có khoảng trống.
- Ở tầng Observation chuẩn, dùng `elapsed_time_sec = (measurement_index - 1) * 60`. Measurement 1 của nguồn là mốc thời gian; nếu measurement 1 bị thiếu thì không được âm thầm làm mất khoảng trống đó.
- Parser raw giữ độ dài waveform thực tế và các mẫu raw. Giá trị 32.768 mẫu trong tài liệu là giá trị kỳ vọng, không phải điều kiện loại file cứng của dự án.
- Measurement bị thiếu là khoảng trống thời gian thực. Nếu sau này được phê duyệt sửa cục bộ một số mẫu trong waveform, việc đó thuộc tầng tiền xử lý riêng và không được ghi đè raw data.
- Hợp đồng Observation raw chuẩn là một record cho mỗi tổ hợp bearing x measurement x channel. Không gộp horizontal và vertical thành một waveform raw.
- `terminal_fault_type` hoặc metadata fault element chuẩn hóa là metadata cấp trajectory. Không tự tạo nhãn `fault_state` theo timestamp từ PDF.
- Giữ cả nhãn fault nguồn (`fault_element_raw`) và biểu diễn nhiều nhãn đã chuẩn hóa (`fault_elements`) nếu có. Không âm thầm gộp fault element với nhãn dạng hỏng.
- Giữ lifetime được công bố trong PDF tách biệt với elapsed time của Observation. Không thay thế trường này cho trường kia nếu chưa có quyết định được tài liệu hóa.
- Metadata về condition, bearing, channel, sampling, lifetime và fault phải giữ nguồn hoặc trích dẫn cùng độ tin cậy/provenance khi phù hợp.

Nếu task muốn thay đổi một trong các quy tắc trên, phải xem xét xung đột trước và cập nhật cả hai decision record trước khi triển khai.
