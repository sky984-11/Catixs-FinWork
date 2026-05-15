export function fileToBase64Payload(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      resolve({
        filename: file.name,
        content_type: file.type || 'image/png',
        data: String(reader.result || ''),
      })
    }
    reader.onerror = () => reject(new Error('读取附件失败'))
    reader.readAsDataURL(file)
  })
}
