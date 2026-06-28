import { useState } from 'react';
import { parseOrder, type OrderParseResponse } from '@/lib/api';
import OrderInput from '@/components/parse/OrderInput';
import ParseResult from '@/components/parse/ParseResult';

export default function Parse() {
  const [result, setResult] = useState<OrderParseResponse | null>(null);
  const [originalText, setOriginalText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [processTime, setProcessTime] = useState<number | undefined>();
  const [error, setError] = useState<string | null>(null);

  async function handleParse(text: string, menuId?: string) {
    setIsLoading(true);
    setError(null);
    setOriginalText(text);
    try {
      const { result: data, processTime: pt } = await parseOrder(text, menuId);
      setResult(data);
      setProcessTime(pt);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Parse failed');
      }
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="h-full">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
        {/* Left Panel — Input */}
        <div>
          <OrderInput onParse={handleParse} isLoading={isLoading} />
          {error && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        {/* Right Panel — Result */}
        <div>
          <ParseResult
            result={result}
            originalText={originalText}
            isLoading={isLoading}
            processTime={processTime}
          />
        </div>
      </div>
    </div>
  );
}
