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