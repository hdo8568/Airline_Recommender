import Foundation

if CommandLine.arguments.contains("--self-test") {
    let original = NSAttributedString(string: "Chicago → Istanbul 🛫 under $900")
    let archive = NSArchiver.archivedData(withRootObject: original)
    guard let decoded = NSUnarchiver.unarchiveObject(with: archive) as? NSAttributedString,
          decoded.string == original.string else { exit(3) }
    print("Archived text round-trip passed.")
    exit(0)
}

// Messages may store plain text inside a legacy archived NSAttributedString.
// Read only one body supplied by the allowlisted database query, not the inbox.
let input = FileHandle.standardInput.readDataToEndOfFile()
guard let bytes = Data(base64Encoded: input) else { exit(1) }
let value = NSUnarchiver.unarchiveObject(with: bytes)
if let attributed = value as? NSAttributedString {
    print(attributed.string)
} else if let text = value as? String {
    print(text)
} else {
    exit(2)
}
