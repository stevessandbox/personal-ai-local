import type { TavilyInfo } from '../types';

interface TavilyStatusProps {
  info: TavilyInfo;
}

export default function TavilyStatus({ info }: TavilyStatusProps) {
  // Only hide if search was not used at all
  if (!info || (!info.called && info.status === 'not called')) {
    return null;
  }

  const statusColor = 
    info.status === 'success' ? 'text-green-400' :
    info.status === 'error' || info.status === 'failed' ? 'text-red-400' :
    'text-yellow-400';

  return (
    <div className="bg-blue-500/10 rounded-md p-4 border border-blue-500/30">
      <h3 className="text-lg font-semibold text-blue-400 mb-3">Tavily API Call Details</h3>
      
      <div className="space-y-2 text-sm">
        <div className="flex">
          <strong className="text-gray-400 min-w-[160px]">Called:</strong>
          <span className="text-white">{info.called ? 'Yes' : 'No'}</span>
        </div>

        {info.called && (
          <>
            <div className="flex">
              <strong className="text-gray-400 min-w-[160px]">Status:</strong>
              <span className={`font-semibold ${statusColor}`}>
                {info.status || 'unknown'}
              </span>
            </div>

            <div className="flex">
              <strong className="text-gray-400 min-w-[160px]">Success:</strong>
              <span className={info.success ? 'text-green-400' : 'text-red-400'}>
                {info.success ? '✓ Yes' : '✗ No'}
              </span>
            </div>

            {info.http_status !== undefined && (
              <div className="flex">
                <strong className="text-gray-400 min-w-[160px]">HTTP Status:</strong>
                <span className="text-white">{info.http_status}</span>
              </div>
            )}

            {info.results_count !== undefined && (
              <div className="flex">
                <strong className="text-gray-400 min-w-[160px]">Results Returned:</strong>
                <span className="text-white">{info.results_count}</span>
              </div>
            )}

            {info.params && (
              <div className="mt-3">
                <strong className="text-gray-400 block mb-2">Parameters Used:</strong>
                <pre className="bg-black/30 rounded p-3 text-xs overflow-x-auto font-mono text-gray-300">
                  {JSON.stringify(info.params, null, 2)}
                </pre>
              </div>
            )}

            {info.error && (
              <div className="mt-3 p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400">
                <strong>Error:</strong> {info.error}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

