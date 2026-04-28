#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
价格调整脚本
用户指定 Excel 文件、调整列名和调整幅度范围，随机调整指定列的数值
结果输出到新文件，不修改原文件
总上调幅度控制在上调幅度的中位数附近
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime


def adjust_prices(file_path: str, column_name: str, min_pct: float, max_pct: float):
    """
    在指定幅度范围内随机调整 Excel 文件中指定列的数值，输出到新文件
    总上调幅度控制在中位数附近
    
    Args:
        file_path: Excel 文件路径
        column_name: 要调整的列名
        min_pct: 最低调整幅度（%），如 5 表示上涨 5%
        max_pct: 最高调整幅度（%），如 12 表示上涨 12%
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"错误：文件不存在 - {file_path}")
        sys.exit(1)
    
    # 读取 Excel 文件
    df = pd.read_excel(file_path)
    
    # 检查是否有指定列
    if column_name not in df.columns:
        print(f"错误：Excel 文件中没有找到'{column_name}'列")
        print(f"可用的列名：{list(df.columns)}")
        sys.exit(1)
    
    n = len(df[column_name])
    
    # 计算中位数
    median_pct = (min_pct + max_pct) / 2
    
    # 生成调整比例，使平均值接近中位数
    # 使用正态分布，均值为中位数，标准差为范围的 1/4
    std_pct = (max_pct - min_pct) / 4
    adjustment_pcts = np.random.normal(median_pct, std_pct, n)
    
    # 确保所有值在范围内
    adjustment_pcts = np.clip(adjustment_pcts, min_pct, max_pct)
    
    # 调整使平均值更接近中位数
    current_mean = np.mean(adjustment_pcts)
    adjustment_pcts = adjustment_pcts - current_mean + median_pct
    
    # 再次确保在范围内
    adjustment_pcts = np.clip(adjustment_pcts, min_pct, max_pct)
    
    # 为每个数值生成调整后的值
    original_values = df[column_name].copy()
    adjusted_values = []
    
    for i, value in enumerate(df[column_name]):
        pct = adjustment_pcts[i]
        new_value = value * (1 + pct / 100)
        # 大于 50 的四舍五入取整，否则保留 2 位小数
        if new_value > 50:
            new_value = round(new_value)
        else:
            new_value = round(new_value, 2)
        adjusted_values.append(new_value)
    
    # 添加调整信息列
    original_col_name = f"原{column_name}"
    adjustment_col_name = f"调整幅度%"
    
    df[original_col_name] = original_values
    df[adjustment_col_name] = [round(p, 2) for p in adjustment_pcts]
    df[column_name] = adjusted_values
    
    # 计算合价（如果有数量列）
    if '数量' in df.columns and column_name in df.columns:
        df['合价'] = df['数量'] * df[column_name]
    
    # 生成输出文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_name = f"{file_path.stem}_调整后_{timestamp}.xlsx"
    output_path = file_path.parent / output_name
    
    # 保存到新 Excel 文件
    df.to_excel(output_path, index=False)
    
    # 打印调整详情
    actual_mean_pct = np.mean(adjustment_pcts)
    print(f"\n价格调整完成！调整范围：{min_pct}% ~ {max_pct}%")
    print(f"目标中位数：{median_pct}%")
    print(f"实际平均幅度：{actual_mean_pct:.2f}%")
    print(f"原文件：{file_path}")
    print(f"调整列：{column_name}")
    print(f"新文件：{output_path}")
    print("=" * 80)
    
    # 显示调整结果
    for _, row in df.iterrows():
        info = f"序号:{int(row.get('序号', _))}  {row.get('物资名称', row.get('名称', 'N/A')):<12}  "
        info += f"原:{row[original_col_name]:>10}  新:{row[column_name]:>10}  幅度:{row[adjustment_col_name]:>7.2f}%"
        if '合价' in df.columns:
            info += f"  合价:{row['合价']:>12.2f}"
        print(info)
    
    print("=" * 80)
    print(f"文件已保存：{output_path}")


def main():
    print("=" * 50)
    print("       价格调整工具")
    print("=" * 50)
    
    # 获取用户输入 - 文件名
    while True:
        file_name = input("\n请输入要调整的 Excel 文件名：").strip()
        if not file_name:
            print("错误：文件名不能为空，请重新输入！")
            continue
        
        file_path = Path(__file__).parent / file_name
        
        if file_path.exists():
            break
        else:
            print(f"错误：文件不存在 - {file_path}，请重新输入！")
    
    # 读取文件获取列名
    df = pd.read_excel(file_path)
    print(f"\n文件中的列名：{list(df.columns)}")
    
    # 获取用户输入 - 列名
    while True:
        column_name = input("请输入要调整的列名：").strip()
        if column_name not in df.columns:
            print(f"错误：列名'{column_name}'不存在，请重新输入！")
            print(f"可用的列名：{list(df.columns)}")
        else:
            break
    
    # 获取用户输入 - 调整幅度
    while True:
        try:
            min_pct = float(input("\n请输入最低调整幅度（%）："))
            max_pct = float(input("请输入最高调整幅度（%）："))
            
            if min_pct > max_pct:
                print("错误：最低幅度不能大于最高幅度，请重新输入！")
                continue
            
            break
        except ValueError:
            print("错误：请输入有效的数字！")
    
    adjust_prices(file_path, column_name, min_pct, max_pct)


if __name__ == "__main__":
    main()
