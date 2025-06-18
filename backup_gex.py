import os
import shutil
from datetime import datetime, timedelta

def backup_old_files():
    """
    備份超過一個月的舊檔案到備份資料夾，保持原本的目錄結構
    """
    # 源目錄和備份目錄
    source_dir = '/home/ben/pCloudDrive/stock/GEX/GEX_file'
    backup_base_dir = '/home/ben/pCloudDrive/stock/GEX/GEX_file_backup'

    print(f"開始備份流程...")
    print(f"源目錄: {source_dir}")
    print(f"備份目錄: {backup_base_dir}")
    
    # 檢查源目錄是否存在
    if not os.path.exists(source_dir):
        print(f"錯誤：源目錄不存在 {source_dir}")
        return
    
    # 確保備份目錄存在
    os.makedirs(backup_base_dir, exist_ok=True)

    # 獲取當前日期，設定為一個月前（30天）
    current_date = datetime.now()
    cutoff_date = current_date - timedelta(days=30)
    
    print(f"當前日期: {current_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"備份截止日期: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"將備份超過 {cutoff_date.strftime('%Y-%m-%d')} 的檔案")
    
    moved_files_count = 0
    total_files_checked = 0
    
    # 遍歷源目錄（包括所有子目錄）
    for root, dirs, files in os.walk(source_dir):
        # 跳過已經在備份目錄中的檔案
        if backup_base_dir in root:
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            total_files_checked += 1
        
            try:
                # 獲取檔案的修改時間
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                # 如果檔案超過30天（一個月）
                if file_mtime < cutoff_date:
                    # 計算相對路徑，以保持目錄結構
                    rel_path = os.path.relpath(root, source_dir)
                    
                    # 在備份目錄中創建對應的目錄結構
                    if rel_path == '.':
                        backup_dir = backup_base_dir
                    else:
                        backup_dir = os.path.join(backup_base_dir, rel_path)
                    
                    os.makedirs(backup_dir, exist_ok=True)
                    
                    # 目標檔案路徑
                    backup_file_path = os.path.join(backup_dir, file)
                    
                    # 如果備份檔案已存在，加上時間戳記避免覆蓋
                    if os.path.exists(backup_file_path):
                        base, ext = os.path.splitext(file)
                        timestamp = file_mtime.strftime('%Y%m%d_%H%M%S')
                        backup_file_path = os.path.join(backup_dir, f"{base}_{timestamp}{ext}")
                    
                    # 移動檔案
                    shutil.move(file_path, backup_file_path)
                    moved_files_count += 1
                    print(f"已移動: {os.path.relpath(file_path, source_dir)} -> {os.path.relpath(backup_file_path, backup_base_dir)}")
                    
            except Exception as e:
                print(f"處理檔案時發生錯誤 {file_path}: {str(e)}")

    print(f"\n備份完成摘要:")
    print(f"檢查檔案總數: {total_files_checked}")
    print(f"移動檔案數量: {moved_files_count}")
    print(f"備份目錄: {backup_base_dir}")

if __name__ == "__main__":
    backup_old_files()
